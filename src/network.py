from abc import ABCMeta, abstractmethod
from collections import abc
from dataclasses import dataclass, fields
import enum
from random import randint, random
import socket
import struct
import threading
import json
from time import sleep, time
from typing import Callable, List, Optional, Dict, Any, Self, Type, get_type_hints
from game_packet import PacketType
from util import logger
import select
from uuid import uuid4
from enum import Enum


@dataclass
class ServerStatus:
    pass


import enum


def deserialize_object(data: Any, target_type: Type[Any]) -> Any:
    """Deserializes a dictionary into a dataclass instance, handling nested objects."""

    if not isinstance(data, dict):
        raise TypeError(f"Expected dict, got {type(data)}")

    if not dataclass(target_type) is target_type:
        raise TypeError(f"{target_type} is not a dataclass")

    type_hints = get_type_hints(target_type)
    field_values = {}

    for field in fields(target_type):
        field_name = field.name
        field_type = type_hints.get(field_name, field.type)

        if field_name in data:
            value = data[field_name]

            if dataclass(field_type) is field_type and isinstance(value, dict):
                field_values[field_name] = deserialize_object(value, field_type)
            elif (
                hasattr(field_type, "__origin__")
                and field_type.__origin__ is list
                and isinstance(value, list)
            ):
                inner_type = field_type.__args__[0]
                if dataclass(inner_type) is inner_type:
                    field_values[field_name] = [
                        deserialize_object(item, inner_type) for item in value
                    ]
                elif (
                    hasattr(inner_type, "__origin__") and inner_type.__origin__ is dict
                ):
                    key_type = inner_type.__args__[0]
                    value_type = inner_type.__args__[1]
                    field_values[field_name] = [
                        {
                            key_type(k): (
                                deserialize_object(v, value_type)
                                if isinstance(v, dict)
                                else v
                            )
                            for k, v in item.items()
                        }
                        for item in value
                    ]
                else:
                    field_values[field_name] = [
                        inner_type(item) if issubclass(inner_type, Enum) else item
                        for item in value
                    ]

            elif (
                hasattr(field_type, "__origin__")
                and field_type.__origin__ is dict
                and isinstance(value, dict)
            ):
                key_type = field_type.__args__[0]
                value_type = field_type.__args__[1]
                if dataclass(value_type) is value_type:
                    field_values[field_name] = {
                        (key_type(k) if issubclass(key_type, Enum) else k): (
                            deserialize_object(v, value_type)
                            if isinstance(v, dict)
                            else (value_type(v) if issubclass(value_type, Enum) else v)
                        )
                        for k, v in value.items()
                    }
                elif (
                    hasattr(value_type, "__origin__") and value_type.__origin__ is list
                ):
                    inner_value_type = value_type.__args__[0]
                    field_values[field_name] = {
                        (key_type(k) if issubclass(key_type, Enum) else k): [
                            (
                                deserialize_object(vi, inner_value_type)
                                if isinstance(vi, dict)
                                else vi
                            )
                            for vi in v
                        ]
                        for k, v in value.items()
                    }
                elif (
                    hasattr(value_type, "__origin__") and value_type.__origin__ is dict
                ):
                    inner_key_type = value_type.__args__[0]
                    inner_value_type = value_type.__args__[1]
                    field_values[field_name] = {
                        (key_type(k) if issubclass(key_type, Enum) else k): {
                            inner_key_type(ik): (
                                deserialize_object(iv, inner_value_type)
                                if isinstance(iv, dict)
                                else iv
                            )
                            for ik, iv in v.items()
                        }
                        for k, v in value.items()
                    }
                else:
                    field_values[field_name] = {
                        (key_type(k) if issubclass(key_type, Enum) else k): (
                            value_type(v) if issubclass(value_type, Enum) else v
                        )
                        for k, v in value.items()
                    }
            elif issubclass(field_type, Enum) and isinstance(value, (str, int)):
                try:
                    field_values[field_name] = field_type(value)
                except ValueError:
                    raise ValueError(
                        f"Invalid enum value '{value}' for {field_type.__name__}"
                    )
            else:
                field_values[field_name] = value
        else:
            raise ValueError(f"Missing required field '{field_name}' in data")

    return target_type(**field_values)


def serialize_object(obj: Any):
    """Recursively converts objects to dictionaries if they have `__dict__`.
    Handles tuples as well.
    """
    if isinstance(obj, (int, float, str, bool, type(None))):  # Handle primitives
        return obj
    elif isinstance(obj, list):  # Handle lists
        return [serialize_object(item) for item in obj]
    elif isinstance(obj, tuple):  # Handle tuples
        return [serialize_object(item) for item in obj]
    elif isinstance(obj, dict):  # Handle dictionaries
        return {
            serialize_object(key): serialize_object(value) for key, value in obj.items()
        }
    elif isinstance(obj, enum.Enum):  # handle enums
        return obj.value
    elif hasattr(obj, "__dict__"):  # Handle custom objects
        result = {}
        for key, value in obj.__dict__.items():
            if not key.startswith("_"):  # prevent serializing private variables
                result[key] = serialize_object(value)
        return result
    else:
        raise TypeError(f"Type {type(obj)} ({obj}) is not JSON serializable")


def recv_all(
    sock: socket.socket,
    length: int,
    timeout: Optional[float] = None,
    id: Optional[str] = None,
) -> Optional[bytes]:
    """Receives exactly 'length' bytes from the socket with an optional timeout."""
    data = b""
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
            # raise ConnectionError(f"[{id}] Socket closed during recv_all")
            return b""

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

    @classmethod
    def from_struct(cls, packet_type: PacketType, s: object):
        return cls(packet_type, json.dumps(serialize_object(s)).encode())

    def serialize_with_length(self) -> bytes:
        """Serializes the packet into bytes with length headers."""
        data_length = len(self.data)
        header = struct.pack(self.HEADER_FORMAT, self.packet_type.value, data_length)
        return header + self.data

    @staticmethod
    def from_socket(
        sock: socket.socket, id: Optional[str] = None, timeout: bool = False
    ) -> Optional["Packet"]:
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

    def __str__(self) -> str:
        return f"<Packet type={self.packet_type}>"


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

    def on_connection(self) -> None:
        pass

    def tick(self) -> None:
        pass


class Server:
    """Multiplayer game server that manages clients and game state."""

    def __init__(self, port: int, handlers: List[NetworkObject]) -> None:
        self.port = port
        self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.server_socket.bind(("0.0.0.0", port))
        self.server_socket.listen()
        self.clients: List[socket.socket] = []
        self.lock = threading.Lock()

        self.server_thread = threading.Thread(target=self._run, daemon=True)
        self.server_thread.start()

        self.handlers: List[NetworkObject] = handlers

        logger.info(f"Server listening on 0.0.0.0:{port}")

        threading.Thread(target=self._broadcast_loop, daemon=True).start()

    def _run(self):
        """Runs the server loop, accepting connections and handling clients."""
        while True:
            client_sock, addr = self.server_socket.accept()
            logger.info(f"Client connected: {addr}")
            with self.lock:
                self.clients.append(client_sock)
            threading.Thread(
                target=self.handle_client, args=(client_sock,), daemon=True
            ).start()
            threading.Thread(
                target=self.handle_client_conn, args=(client_sock,), daemon=True
            ).start()

    def handle_client(self, client_sock: socket.socket):
        """Handles client messages and packet processing."""

        for handler in self.handlers:
            handler.on_connection()

        while True:
            try:
                packet = Packet.from_socket(client_sock, timeout=False)
                if packet is None:
                    break

                self.process_packet(packet, client_sock)
            except (ConnectionError, Exception) as e:
                logger.warning(f"Client disconnected: {e}")

    def handle_client_conn(self, client_sock: socket.socket):
        connection_packet = Packet(PacketType.CONNECTION)
        client_sock.sendall(connection_packet.serialize_with_length())

        while True:
            try:
                status_packet = Packet(
                    PacketType.STATUS, json.dumps(ServerStatus().__dict__).encode()
                )
                client_sock.sendall(status_packet.serialize_with_length())
                sleep(0.1)
            except (ConnectionError, Exception) as e:
                logger.warning(f"Client connection handler disconnected: {e}")
                with self.lock:
                    if client_sock in self.clients:
                        self.clients.remove(client_sock)
                break

    def process_packet(self, packet: Packet, client_sock: socket.socket):
        """Finds the appropriate handler for a received packet."""
        handled = False
        for handler in self.handlers:
            if handler.check_handles(packet.packet_type):
                handler.handle_packet(packet, client_sock)
                handled = True

        if not handled:
            logger.warning(f"Packet not handled: {packet}")

    def broadcast_packet(self, packet: Packet):
        for client in self.clients:
            client.sendall(packet.serialize_with_length())

    @abstractmethod
    def tick(self) -> None:
        pass

    def _broadcast_loop(self):
        while True:
            self.tick()
            [o.tick() for o in self.handlers]
            sleep(0.1)


class Client(metaclass=ABCMeta):
    """
    Multiplayer game client that communicates with the server
    Should be inherited
    """

    def __init__(self, address: str, port: int):
        """Initializes the client, connects to the server, and starts listening for updates."""
        self.server_address = (address, port)
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        self.sock.connect(self.server_address)

        self.listen_thread = threading.Thread(target=self.listen, daemon=True)
        self.listen_thread.start()

    def send(self, pack: Packet) -> None:
        self.sock.sendall(pack.serialize_with_length())

    @abstractmethod
    def packet_callback(self, packet: Packet):
        pass

    def listen(self):
        """Listens for game state updates from the server and updates the client's local state."""
        while True:
            try:
                packet = Packet.from_socket(self.sock)
                if packet is None:
                    logger.warning(f"Received empty packet, disconnecting...")
                    break
                self.packet_callback(packet)

            except (ConnectionError, socket.error) as e:
                logger.warning(f"Connection error: {e}")
                break
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                break

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


def do_if(pack: Packet, t: PacketType, callback: Callable[[], None]) -> None:
    if pack.packet_type == t:
        callback()
