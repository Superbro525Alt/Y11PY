from abc import ABCMeta, abstractmethod
import enum
import json
from random import randint
from socket import socket
from threading import Lock
from types import SimpleNamespace
from typing import Callable, Deque, Dict, List, Optional
from auth import DataRequest, LoginRequest, LoginResponse, ServerUserData, User, UserMap
from game_packet import MatchRequest, PacketType
from matchmaking import Matchmaking
from network import (
    Client,
    NetworkObject,
    Packet,
    Server,
    ServerStatus,
    deserialize_object,
    do_if,
)
from dataclasses import dataclass
import datetime
from chest import Chest, ChestRarity, generate_chest
from clan import Clan
from shop import Shop
from card import ARCHER, GIANT, Deck, Card
from engine import (
    Camera,
    Camera3D,
    Component,
    EngineCode,
    EngineFrameData,
    GameObject,
    TextRenderer,
    Transform,
    Transform3D,
    UIAnimation,
    UIElement,
)
from pipeline import Event, FramePipeline, StateData
from engine import Engine
from util import json_to_dataclass


@dataclass
class BattleState:
    elixir: int
    hand: List[Card]
    next: Optional[Card]
    match_uuid: str
    other_uuid: str


@dataclass
class ConnectionStatus:
    last_connection: Optional[datetime.datetime]
    connected: bool


@dataclass
class MenuState:
    chests: List[Chest]
    clan: Optional[Clan]
    shop: Optional[Shop]
    decks: List[Deck]
    deck_idx: int
    trophies: int


@dataclass
class AuthState:
    loggedin: bool
    username: Optional[str]
    requested: bool
    uuid: Optional[str]


@dataclass
class GameState:
    """
    This is the current game state:
        - It holds the current battle state
        - The authentication state
        - The clan state
        - The shop
        - The deck(s)
        - The chests
        - The trophies
        - The status
    """

    battle_state: Optional[BattleState]
    menu_state: Optional[MenuState]


class BattleClient:
    def __init__(self) -> None:
        self.battle_state: Optional[BattleState] = None

    def tick(
        self, state: Optional[GameState], respond: Callable[[Packet], None]
    ) -> None:
        if state and state.battle_state:
            self.battle_state = state.battle_state


class GameNetworkClient(Client):
    def __init__(self, name: str):
        super().__init__("127.0.0.1", 12345)

        self.battle_client = BattleClient()

        self.state_lock = Lock()
        self.status_lock = Lock()
        self.connection_status_lock = Lock()

        self.state: Optional[GameState] = None
        self.status: Optional[ServerStatus] = ServerStatus()
        self.connection_status: ConnectionStatus = ConnectionStatus(None, False)
        self.auth_state: AuthState = AuthState(False, None, False, None)
        self.name = name

    def tick(self):
        if self.connection_status.last_connection:
            if (
                self.connection_status.last_connection.timestamp()
                - datetime.datetime.now().timestamp()
                + 2
                < 0
            ):
                self.update_connection_status(False)

        if not self.auth_state.loggedin and not self.auth_state.requested:
            self.auth_state.requested = True
            self.send(
                Packet.from_struct(
                    PacketType.LOGIN, LoginRequest(str(self.name), str(self.name))
                )
            )

        if self.auth_state.uuid:
            self.send(
                Packet.from_struct(
                    PacketType.CLIENT_SERVER_SYNC, DataRequest(self.auth_state.uuid)
                )
            )

        # print(f"{self.name}: {self.state}")

    #
    def tick_state(self, data: bytes) -> None:
        with self.state_lock:
            try:
                self.state = json.loads(
                    data.decode(), object_hook=lambda d: SimpleNamespace(**d)
                )
            except Exception as e:
                # print("e")
                raise ValueError(
                    f"Transmitted Game State was in an invalid format: {e}"
                )

            self.battle_client.tick(self.state, self.send)

    def update_status(self, data: bytes) -> None:
        with self.status_lock:
            self.status = ServerStatus(**json.loads(data.decode()))
        with self.connection_status_lock:
            self.connection_status.last_connection = datetime.datetime.now()

    def update_connection_status(self, connected=True) -> None:
        with self.connection_status_lock:
            if connected:
                self.connection_status = ConnectionStatus(datetime.datetime.now(), True)
            else:
                self.connection_status = ConnectionStatus(None, False)

    def login_success(self, data: Packet):
        decoded: LoginResponse = LoginResponse(**json.loads(data.data.decode()))
        self.auth_state = AuthState(True, decoded.username, False, decoded.uuid)

    def login_fail(self, data: Packet):
        self.auth_state.requested = False

    def packet_callback(self, packet: Packet):
        do_if(
            packet, PacketType.CONNECTION, lambda: self.update_connection_status(True)
        )
        do_if(packet, PacketType.STATUS, lambda: self.update_status(packet.data))
        do_if(
            packet, PacketType.DISCONNECT, lambda: self.update_connection_status(False)
        )
        do_if(packet, PacketType.LOGIN_SUCCESS, lambda: self.login_success(packet))
        do_if(packet, PacketType.LOGIN_FAIL, lambda: self.login_fail(packet))

        do_if(
            packet, PacketType.SERVER_CLIENT_SYNC, lambda: self.tick_state(packet.data)
        )
        do_if(packet, PacketType.MATCH_FOUND, lambda: self.found_match(packet))

    def found_match(self, packet: Packet):
        print("======================= found match =======================")

    def start_matchmaking(self) -> bool:
        if not self.state or not self.state.menu_state or not self.auth_state.uuid:
            return False

        self.send(
            Packet.from_struct(
                PacketType.MATCH_REQUEST,
                MatchRequest(self.state.menu_state.trophies, self.auth_state.uuid),
            )
        )

        return True


class NetworkStateObject(NetworkObject):
    def __init__(self):
        super().__init__()
        self._handles = [
            PacketType.LOGIN,
            PacketType.CLIENT_SERVER_SYNC,
            PacketType.MATCH_REQUEST,
        ]
        self.users: UserMap = UserMap(
            [
                User(
                    str(i),
                    str(i),
                    str(i),
                    ServerUserData(
                        [generate_chest(ChestRarity.GOLD)],
                        None,
                        0,
                        [Deck([ARCHER, GIANT])],
                        0,
                        None,
                    ),
                )
                for i in range(2)
            ]
        )
        self.shop = Shop([])
        self.matchmaking = Matchmaking()

    def handle_packet(self, packet: Packet, client_sock: socket) -> None:
        if packet.packet_type == PacketType.LOGIN:
            data = LoginRequest(**json.loads(packet.data.decode()))
            found = self.users.find(data.username, data.password_hash)
            if found is not None:
                client_sock.sendall(
                    Packet.from_struct(
                        PacketType.LOGIN_SUCCESS,
                        LoginResponse(found.uuid, found.username),
                    ).serialize_with_length()
                )
            else:
                client_sock.sendall(
                    Packet(PacketType.LOGIN_FAIL).serialize_with_length()
                )
        elif packet.packet_type == PacketType.CLIENT_SERVER_SYNC:
            data = DataRequest(**json.loads(packet.data.decode()))
            found = self.users.find_uuid(data.uuid)
            if found is not None:
                state = GameState(None, None)
                state.menu_state = MenuState(
                    found.data.chests,
                    found.data.clan,
                    self.shop,
                    found.data.decks,
                    found.data.current_deck,
                    found.data.trophies,
                )
                if found.data.current_battle:
                    found_match, other_uuid = self.matchmaking.get_match(
                        found.data.current_battle, data.uuid
                    )
                    if found_match and other_uuid:
                        state.battle_state = BattleState(
                            found_match.elixir,
                            found_match.hand,
                            found_match.next_card,
                            found.data.current_battle,
                            other_uuid,
                        )
                client_sock.sendall(
                    Packet.from_struct(
                        PacketType.SERVER_CLIENT_SYNC, state
                    ).serialize_with_length()
                )
        elif packet.packet_type == PacketType.MATCH_REQUEST:
            data = MatchRequest(**json.loads(packet.data.decode()))
            self.matchmaking.request(data, client_sock)

    def tick(self):
        self.matchmaking.tick()


class GameServer(Server):
    def __init__(self) -> None:
        super().__init__(12345, [NetworkStateObject()])

    def tick(self) -> None:
        pass


class Game(Engine):
    def __init__(self, name: str):
        engine_pipe = FramePipeline[EngineFrameData]("engine_pipe")
        event_pipe = FramePipeline[Event]("event_pipe")
        state_pipe = FramePipeline[StateData]("state_pipe")

        super().__init__(
            engine_pipe,
            event_pipe,
            state_pipe,
            window_title="Clash Test",
            width=1200,
            height=800,
        )

        self.camera = Camera((0, 0), zoom=0.75, screen_width=1200, screen_height=800)

        self.name = name

    def tick(self):
        self.client.tick()

    def start(self):
        self.run(self.tick)

    def setup(self):
        self.text_renderer = TextRenderer(self.sdl)
        self.text_renderer.load_font(
            "/usr/share/fonts/adobe-source-sans/SourceSansPro-Regular.otf", 24
        )

        self.client = GameNetworkClient(self.name)

        self.setup_ui()

    def setup_ui(self):
        title_banner = UIElement(
            int(self.sdl.get_width() / 6),
            50,
            int(self.sdl.get_width() - self.sdl.get_width() / 6 * 2),
            100,
            color=(255, 215, 0),
        )

        self.ui_manager.add_element(title_banner)

        bottom_bar = UIElement(
            0,
            self.sdl.get_height() - 120,
            self.sdl.get_width(),
            120,
            color=(40, 40, 60),
        )
        self.ui_manager.add_element(bottom_bar)

        button_width = 120
        button_spacing = 40
        start_x = (self.sdl.get_width() - (button_width * 4 + button_spacing * 3)) // 2
        button_labels = ["Cards", "Battle", "Shop", "Clan"]

        for i, label in enumerate(button_labels):
            button = UIElement(
                start_x + i * (button_width + button_spacing),
                self.sdl.get_height() - 100,
                button_width,
                80,
                color=(200, 200, 255),
                on_hover=(255, 0, 0),
            )

            self.ui_manager.add_element(button)

    def override_render(self):
        for i, label in enumerate(["Cards", "Battle", "Shop", "Clan"]):
            x = (self.sdl.get_width() - (120 * 4 + 40 * 3)) // 2 + i * (120 + 40)
            y = self.sdl.get_height() - 100

            text_width = self.text_renderer.get_text_width(label)
            text_height = self.text_renderer.get_font_height(label)

            x_centered = x + (120 - text_width) // 2
            y_centered = y + (80 - text_height) // 2

            self.text_renderer.draw_text(label, x_centered, y_centered, (255, 255, 255))
