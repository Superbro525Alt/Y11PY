import enum
import socket
import struct
import threading
from time import time
from typing import Any, Callable, List, Optional
from util import logger
import select


# Define the PacketType as an enum.
class PacketType(enum.Enum):
    # Connection
    STATUS = 0
    HANDSHAKE = 1

    # Lobby/Matchmaking
    PLAYER_JOIN = 2
    PLAYER_LEAVE = 3
    LOBBY_UPDATE = 4
    CHAT_MESSAGE = 5

    # Gameplay
    GAME_TICKDATA = 6
    GAME_ACTION = 7
    GAME_END = 8
    PLAYER_HIT = 9
    SCORE_UPDATE = 10
    ENTITY_SPAWN = 11
    ENTITY_UPDATE = 12
    ENTITY_REMOVE = 13

    # Loading/Syncing
    LOADING_STATUS = 14
    WORLD_SYNC = 15
    PING = 16
    PONG = 17


def recv_all(sock: socket.socket, length: int, timeout: Optional[float] = None) -> Optional[bytes]:
    """Receives exactly 'length' bytes from the socket, with an optional timeout.

    Args:
        sock: The socket object.
        length: The number of bytes to receive.
        timeout: The timeout in seconds.  If None, no timeout is used.

    Returns:
        The received bytes.

    Raises:
        ConnectionError: If the socket closes before receiving all bytes.
        TimeoutError: If the timeout is reached before receiving all bytes.
    """
    data = b''
    remaining = length

    while remaining > 0:
        if timeout is not None:
            readable, _, _ = select.select([sock], [], [], timeout)
            if not readable:  
                logger.warning("Timeout during recv_all")
                return None

        try:
            chunk = sock.recv(remaining)
        except socket.timeout: 
            logger.warning("Timeout during recv_all")
            return None

        if not chunk:
            raise ConnectionError("Socket closed during recv_all")

        data += chunk
        remaining -= len(chunk)

    return data

class Packet:
    # We use a header consisting of two little-endian unsigned ints:
    #   - packet_type (4 bytes)
    #   - data_length (4 bytes)
    HEADER_FORMAT = "<II"
    HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

    def __init__(self, packet_type: PacketType, data: Optional[bytes] = None):
        self.packet_type = packet_type
        self.data = data if data else b""

    def serialize_with_length(self) -> bytes:
        """
        Serializes the packet into bytes.
        The header is: [4 bytes packet_type][4 bytes data length],
        then followed by the raw data.
        """
        data_length = len(self.data)
        header = struct.pack(self.HEADER_FORMAT, self.packet_type.value, data_length)
        return header + self.data

    @staticmethod
    def from_socket(sock: socket.socket) -> Optional["Packet"]:
        """
        Reads from the given socket to build a Packet.
        It first reads the header and then the payload.
        """
        header = recv_all(sock, Packet.HEADER_SIZE, 2)
        if header is None:
            return None

        if len(header) != Packet.HEADER_SIZE:
            raise ConnectionError("Incomplete header received")
        packet_type_val, data_length = struct.unpack(Packet.HEADER_FORMAT, header)
        try:
            packet_type = PacketType(packet_type_val)
        except ValueError:
            raise ValueError(f"Invalid packet type received: {packet_type_val}")
        data = recv_all(sock, data_length)

        return Packet(packet_type, data)

    def __repr__(self):
        return f"<Packet type={self.packet_type.name} data_len={len(self.data)}>"


# Define an interface for objects that handle packets.
class NetworkObject:
    """
    Override this method to handle an incoming packet.
    :param packet: The Packet instance received.
    :param client_sock: The socket the packet came from.
    """

    HANDLES: Callable[[], List[PacketType]] = list  # Callable that returns a list

    PRIORITY_MAX = 0
    PRIORITY_MIN = 99

    def __init__(self):
        self._handles: List[PacketType] = self.HANDLES()  # Initialize instance-specific list

    def handle_packet(self, packet: Packet, client_sock: Any) -> None:
        raise NotImplementedError("handle_packet must be implemented by subclass")

    def check_handles(self, t: PacketType) -> bool:
        return t in self._handles

    def get_priority(self) -> int:
        """Returns the priority of this handler. Lower numbers have higher priority."""
        return 0

# Server class that accepts client connections and dispatches packets.
class Server:
    def __init__(self, port: int, network_objects: List[NetworkObject], start_immediately: bool = True):
        self.port = port
        self.network_objects = network_objects
        self.network_object_lock = threading.Lock()  # Protect shared network_object access.
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", port))
        self.server_socket.listen()

        self.server_thread = threading.Thread(target=lambda: self._run(), daemon=True)
        logger.info(f"Server listening on 0.0.0.0:{port}")

    def start(self):
        self.server_thread.start()

    def _run(self):
        try:
            while True:
                client_sock, addr = self.server_socket.accept()
                logger.info(f"Client connected: {addr}")
                threading.Thread(
                    target=self.handle_client,
                    args=(client_sock, addr),
                    daemon=True
                ).start()
        except KeyboardInterrupt:
            logger.info("Server shutting down...")
        finally:
            self.server_socket.close()

    def handle_client(self, client_sock: socket.socket, addr):
        try:
            while True:
                packet = Packet.from_socket(client_sock)

                if packet is None:
                    logger.warning("No packet recieved")
                    return

                with self.network_object_lock:
                    matching_objects = [
                        obj for obj in self.network_objects
                        if obj.check_handles(packet.packet_type)  # Assuming packet.packet_type exists
                    ]

                    if not matching_objects:
                        logger.warning("No network object implemented to respond to packet: " + packet.packet_type.__str__())
                        continue  

                    matching_objects.sort(key=lambda obj: obj.get_priority())

                    handled = False
                    for obj in matching_objects:
                        try:
                            obj.handle_packet(packet, client_sock)
                            handled = True
                            break  
                        except Exception as e: 
                            logger.error(f"Error handling packet in {obj.__class__.__name__}: {e}") 
                            continue 

                    if not handled: 
                        logger.warning(f"No handler successfully processed packet type {packet.packet_type}")


        except (ConnectionError, Exception) as e:
            logger.info(f"Client {addr} disconnected: {e}")
        finally:
            client_sock.close()


class Client:
    def __init__(self, address: str, port: int):
        self.server_address = (address, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.connect(self.server_address)
        logger.info(f"Connected to server at {self.server_address}")

    def send_packet(self, packet: Packet) -> None:
        data = packet.serialize_with_length()
        self.sock.sendall(data)

    def receive_packet(self) -> Optional[Packet]:
        return Packet.from_socket(self.sock)

    def close(self):
        self.sock.close()

    def check_lat(self):
        """
        Checks the latency with the server (in ms)
        """
        start_time = time()
        self.send_packet(Packet(PacketType.PING))
        self.receive_packet()
        return time() - start_time


class EchoNetworkObject(NetworkObject):
    def __init__(self):
        super().__init__()
        self._handles.extend([PacketType.PING])

    def handle_packet(self, packet: Packet, client_sock: socket.socket) -> None:
        if packet.packet_type == PacketType.PING:
            client_sock.sendall(Packet(PacketType.PONG).serialize_with_length())

    def get_priority(self) -> int:
        return 0

class BaseNetworkObject(NetworkObject):
    def __init__(self):
        super().__init__()
        self._handles.extend(list(PacketType))

    def handle_packet(self, packet: Packet, client_sock: socket.socket) -> None:
        client_sock.sendall(Packet(PacketType.HANDSHAKE).serialize_with_length())

    def get_priority(self) -> int:
        return NetworkObject.PRIORITY_MIN 
