import enum
import socket
import struct
import threading
import json
from time import sleep
from typing import List, Optional, Dict, Any
from board import Board
from util import logger
import select


class PacketType(enum.Enum):
    """Defines different types of network packets."""
    STATUS = 0
    HANDSHAKE = 1
    PLAYER_JOIN = 2
    PLAYER_LEAVE = 3
    GAME_TICKDATA = 6
    GAME_ACTION = 7
    GAME_END = 8
    WORLD_SYNC = 15
    PING = 16
    PONG = 17


def recv_all(sock: socket.socket, length: int, timeout: Optional[float] = None, id: Optional[str] = None) -> Optional[bytes]:
    """Receives exactly 'length' bytes from the socket with an optional timeout."""
    data = b''
    remaining = length

    while remaining > 0:
        if timeout is not None:
            readable, _, _ = select.select([sock], [], [], timeout)
            if not readable:
                return None

        try:
            chunk = sock.recv(remaining)
        except socket.timeout:
            return None

        if not chunk:
            raise ConnectionError(f"[{id}] Socket closed during recv_all")

        data += chunk
        remaining -= len(chunk)

    return data


class Packet:
    """Represents a network packet that is serialized for transmission."""
    HEADER_FORMAT = "<II"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

    def __init__(self, packet_type: PacketType, data: Optional[bytes] = None):
        self.packet_type = packet_type
        self.data = data if data else b""

    def serialize_with_length(self) -> bytes:
        """Serializes the packet into bytes with length headers."""
        data_length = len(self.data)
        header = struct.pack(self.HEADER_FORMAT, self.packet_type.value, data_length)
        return header + self.data

    @staticmethod
    def from_socket(sock: socket.socket, id: Optional[str] = None, timeout: bool = False) -> Optional["Packet"]:
        """Receives a packet from a socket."""
        t = None
        if timeout:
            t = 5

        header = recv_all(sock, Packet.HEADER_SIZE, id=id, timeout=t)
        if header is None:
            return None

        if len(header) != Packet.HEADER_SIZE:
            return None

        packet_type_val, data_length = struct.unpack(Packet.HEADER_FORMAT, header)
        try:
            packet_type = PacketType(packet_type_val)
        except ValueError:
            return None

        data = recv_all(sock, data_length)
        return Packet(packet_type, data)


class NetworkObject:
    """Base class for handling specific packet types."""
    
    def __init__(self):
        self._handles = self.get_supported_packets()

    def handle_packet(self, packet: Packet, client_sock: socket.socket) -> None:
        """Override this method to handle incoming packets."""
        raise NotImplementedError("handle_packet must be implemented by subclasses")

    def get_supported_packets(self) -> List[PacketType]:
        """Override this method to return the list of handled packet types."""
        return []

    def check_handles(self, packet_type: PacketType) -> bool:
        """Checks if this network object can handle a given packet type."""
        return packet_type in self._handles


class GameActionHandler(NetworkObject):
    """Handles game actions such as movement, treating disease, passing turns."""

    def __init__(self, board: Board):
        super().__init__()
        self.board = board
        self._handles = [PacketType.GAME_ACTION]

    def handle_packet(self, packet: Packet, client_sock: socket.socket) -> None:
        """Processes a game action from a client."""
        action_data = json.loads(packet.data.decode())
        player = action_data.get("player")
        action_type = action_data.get("action")
        details = action_data.get("details")

        if action_type == "move":
            self.board.move(player, details["destination"])
        elif action_type == "treat":
            self.board.treat_disease(player)
        elif action_type == "cure":
            self.board.cure_disease(player, details["disease"])
        elif action_type == "pass":
            self.board.pass_turn(player)

        if self.board.actions_remaining == 0:
            self.board.pass_turn(player)



class Server:
    """Multiplayer game server that manages clients and game state."""

    def __init__(self, port: int):
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", port))
        self.server_socket.listen()
        self.clients = []
        self.lock = threading.Lock()
        self.board = Board(["Bot1", "Bot2", "Bot3", "Player"])
        self.handlers = [GameActionHandler(self.board)]

        print(f"Starting player: {self.board.get_current_player()}")
        self.server_thread = threading.Thread(target=self._run, daemon=True)
        self.server_thread.start()

        logger.info(f"Server listening on 0.0.0.0:{port}")

        threading.Thread(target=self._broadcast_loop, daemon=True).start()

    def _run(self):
        """Runs the server loop, accepting connections and handling clients."""
        while True:
            print("waiting")
            client_sock, addr = self.server_socket.accept()
            logger.info(f"Client connected: {addr}")
            with self.lock:
                self.clients.append(client_sock)
            threading.Thread(target=self.handle_client, args=(client_sock,), daemon=True).start()


    def handle_client(self, client_sock: socket.socket):
        """Handles client messages and packet processing."""

        while True:
            try:
                packet = Packet.from_socket(client_sock, timeout=False)
                if packet is None:
                    break

                self.process_packet(packet, client_sock)
            except (ConnectionError, Exception) as e:
                logger.warning(f"Client disconnected: {e}")

    def process_packet(self, packet: Packet, client_sock: socket.socket):
        """Finds the appropriate handler for a received packet."""
        for handler in self.handlers:
            if handler.check_handles(packet.packet_type):
                handler.handle_packet(packet, client_sock)

    def _broadcast_loop(self):
        while True:
            self.broadcast_state()
            sleep(0.1)

    def broadcast_state(self):
        """Sends the latest game state to all clients."""
        game_state = json.dumps(self.board.broadcast_state()).encode()
        packet = Packet(PacketType.GAME_TICKDATA, game_state)
        with self.lock:
            for client in self.clients:
                try:
                    client.sendall(packet.serialize_with_length())
                except:
                    self.clients.remove(client)
                    logger.warning("Client disconnected")

class Client:
    """Multiplayer game client that communicates with the server and tracks game state."""

    def __init__(self, address: str, port: int, player_name: str):
        """Initializes the client, connects to the server, and starts listening for updates."""
        self.server_address = (address, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.connect(self.server_address)
        self.player_name = player_name

        self.board = {}
        self.current_turn = None
        self.actions_remaining = 0
        self.is_my_turn = False

        self.listen_thread = threading.Thread(target=self.receive_updates, daemon=True)
        self.listen_thread.start()

    def send_action(self, action_type: str, details: Dict[str, Any] = {}):
        """Sends a game action to the server if it's the player's turn and they have actions left."""
        if not self.is_my_turn:
            logger.warning(f"[{self.player_name}] It's not your turn!")
            return

        if self.actions_remaining <= 0:
            logger.warning(f"[{self.player_name}] No actions left this turn!")
            return

        action = {
            "player": self.player_name,
            "action": action_type,
            "details": details
        }
        packet = Packet(PacketType.GAME_ACTION, json.dumps(action).encode())
        self.sock.sendall(packet.serialize_with_length())

        self.actions_remaining -= 1

    def receive_updates(self):
        """Listens for game state updates from the server and updates the client's local state."""
        while True:
            try:
                packet = Packet.from_socket(self.sock, self.player_name)
                if packet is None:
                    logger.warning(f"[{self.player_name}] Received empty packet, disconnecting...")
                    break
                
                if packet.packet_type == PacketType.GAME_TICKDATA:
                    game_state = json.loads(packet.data.decode())
                    self.update_local_state(game_state)
                
            except (ConnectionError, socket.error) as e:
                logger.warning(f"[{self.player_name}] Connection error: {e}")
                break
            except Exception as e:
                logger.error(f"[{self.player_name}] Unexpected error: {e}")
                break
    
    # Clean up on disconnect
        try:
            self.sock.close()
        except:
            pass

    def close(self):
        """Closes the client connection gracefully."""
        try:
            self.sock.shutdown(socket.SHUT_RDWR)
        except:
            pass
        finally:
            self.sock.close()

    def update_local_state(self, game_state: Dict[str, Any]):
        """Updates the client's local copy of the board state and turn tracking."""
        self.board = game_state

        self.current_turn = game_state["current_turn"]
        self.actions_remaining = game_state["actions_remaining"]
        self.is_my_turn = self.current_turn == self.player_name


        if self.is_my_turn:
            logger.info(f"[{self.player_name}] It's your turn! You have {self.actions_remaining} actions.")
