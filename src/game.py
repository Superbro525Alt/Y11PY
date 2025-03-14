from abc import ABCMeta, abstractmethod
from collections import deque
import enum
from functools import partial
import json
from logging import warn
from random import randint, random
from socket import socket
from threading import Lock
from time import time
from types import SimpleNamespace
from typing import Callable, Deque, Dict, List, Optional

from numpy import average
from copy import copy
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
    serialize_object,
)
from dataclasses import dataclass
import datetime
from chest import Chest, ChestRarity, generate_chest
from clan import Clan
from shop import Shop
from card import (
    ARCANE_CANNON,
    EARTHQUAKE,
    GOBLIN_SHAMAN,
    ICE_SPIKES,
    LUMBERJACK_GOBLIN,
    POISON_TOWER,
    ROCK_GOLEM,
    SKY_ARCHER,
    Deck,
    Card,
)
from engine import (
    Camera,
    Camera3D,
    Component,
    EngineCode,
    EngineFrameData,
    GameObject,
    Scene,
    TextRenderer,
    Transform,
    Transform3D,
    UIAnimation,
    UIButton,
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

        # if self.state and self.state.battle_state:
        # print(f"{self.name}: {self.state.battle_state.elixir}")

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
        # print(packet)
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
            print("[client] Invalid game/auth state")
            return False

        print("[client] Request matchmaking")

        self.send(
            Packet.from_struct(
                PacketType.MATCH_REQUEST,
                MatchRequest(
                    self.state.menu_state.trophies,
                    self.auth_state.uuid,
                    self.state.menu_state.decks[self.state.menu_state.deck_idx],
                ),
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
                        [
                            generate_chest(ChestRarity.GOLD)
                            for i in range(randint(0, 4))
                        ],
                        None,
                        0,
                        [
                            Deck(
                                [
                                    GOBLIN_SHAMAN,
                                    ROCK_GOLEM,
                                    ICE_SPIKES,
                                    POISON_TOWER,
                                    SKY_ARCHER,
                                    EARTHQUAKE,
                                    LUMBERJACK_GOBLIN,
                                    ARCANE_CANNON,
                                ]
                            )
                        ],
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
            data = json.loads(
                packet.data.decode(), object_hook=lambda d: SimpleNamespace(**d)
            )

            self.matchmaking.request(data, client_sock)

    def tick(self):
        self.matchmaking.tick(
            lambda user_id, battle_id: self.users.update_battle(user_id, battle_id)
        )


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
        self.client = GameNetworkClient(self.name)
        self.matchmaking_started = False  # To track matchmaking state

        self.latency: Deque[int] = deque([0], maxlen=10)  # Track server latency
        self.ui_buttons = []

        # Register scenes
        self.main_menu_scene = Scene("main_menu")
        self.battle_scene = Scene("battle")

    def setup_scenes(self):
        """Initializes all scenes and UI elements."""

        # Latency Display (Present in All Scenes)
        self.latency_display = UIElement(20, 20, 200, 30, color=(50, 50, 50))
        self.main_menu_scene.add_ui_element(self.latency_display)
        self.battle_scene.add_ui_element(self.latency_display)

        # Main Menu UI
        title_banner = UIElement(
            int(self.sdl.get_width() / 6),
            50,
            int(self.sdl.get_width() - self.sdl.get_width() / 6 * 2),
            100,
            color=(255, 215, 0),
        )
        self.main_menu_scene.add_ui_element(title_banner)

        # Show player trophies
        self.trophy_display = UIElement(50, 180, 200, 50, color=(100, 100, 100))
        self.main_menu_scene.add_ui_element(self.trophy_display)

        # Chest info
        self.chest_display = UIElement(50, 250, 400, 50, color=(150, 150, 150))
        self.main_menu_scene.add_ui_element(self.chest_display)

        # Matchmaking button
        start_button = UIButton(
            (self.sdl.get_width() - 200) // 2,
            350,
            200,
            80,
            self.text_renderer,
            color=(0, 200, 0),
            on_hover=(0, 255, 0),
            callback=self.start_matchmaking,
            text="Start",
        )
        self.main_menu_scene.add_ui_element(start_button)

        # Battle Scene UI
        self.battle_bg = UIElement(
            0, 0, self.sdl.get_width(), self.sdl.get_height(), color=(40, 40, 40)
        )
        self.battle_scene.add_ui_element(self.battle_bg)

        self.elixir_display = UIElement(
            20,  # Center horizontally
            80,  # Near the bottom
            100,  # Wider
            30,
            color=(0, 0, 255),
        )

        self.battle_scene.add_ui_element(self.elixir_display)

        # Spreading Hand Cards More Evenly Across the Bottom
        self.hand_buttons = []
        hand_card_width = 120
        hand_card_height = 160
        spacing = 20
        hand_start_x = (self.sdl.get_width() - (hand_card_width * 4 + spacing * 3)) // 2
        hand_y = self.sdl.get_height() - 180

        for i in range(4):  # Assuming a 4-card hand
            card_x = hand_start_x + i * (hand_card_width + spacing)

            card_button = UIButton(
                card_x,
                hand_y,
                hand_card_width,
                hand_card_height,
                self.text_renderer,
                color=(150, 150, 150),
                on_hover=(200, 200, 200),  # Add slight transparency on hover
                callback=None,
                text="Card",
            )
            self.battle_scene.add_ui_element(card_button)
            self.hand_buttons.append(card_button)

        # Register Scenes
        self.scene_manager.add_scene(self.main_menu_scene)
        self.scene_manager.add_scene(self.battle_scene)

    def tick(self):
        """Handles game updates."""
        self.client.tick()
        self.update_latency()

        if (
            self.client.state
            and self.client.state.battle_state is not None
            and self.scene_manager.current_scene is not None
            and self.scene_manager.current_scene != "battle"
        ):
            self.start_battle()
        elif (
            self.client.state
            and self.client.battle_client is None
            and self.scene_manager.current_scene is not None
            and self.scene_manager.current_scene != "main_menu"
        ):
            self.go_to_main_menu()

    def start(self):
        """Starts the game loop."""
        self.run(self.tick)

    def start_battle(self):
        """Switches to the battle scene."""
        self.scene_manager.load_scene("battle")

    def go_to_main_menu(self):
        """Returns to the main menu."""
        self.scene_manager.load_scene("main_menu")

    def update_latency(self):
        """Fetch latency from the game client."""
        if self.client.connection_status.last_connection is not None:
            self.latency.append(
                int(
                    round(
                        (
                            datetime.datetime.now()
                            - self.client.connection_status.last_connection
                        ).microseconds
                        / 1000,
                        0,
                    )
                )
            )

    def get_latency_color(self):
        """Returns latency color (green, yellow, or red) based on latency."""
        if average(self.latency) < 120:
            return (0, 255, 0)  # Green
        elif average(self.latency) < 200:
            return (255, 255, 0)  # Yellow
        else:
            return (255, 0, 0)  # Red

    def setup(self):
        """Initial setup for the game."""
        self.text_renderer = TextRenderer(self.sdl)
        self.text_renderer.load_font(
            "/usr/share/fonts/adobe-source-sans/SourceSansPro-Regular.otf", 24
        )

        self.setup_scenes()
        self.scene_manager.load_scene("main_menu")

        # self.client = GameNetworkClient(self.name)

    def start_matchmaking(self):
        """Starts matchmaking when the 'Battle' button is pressed."""
        if not self.matchmaking_started:
            print(f"[Matchmaking, {self.name}] Searching for a battle...")
            self.matchmaking_started = True
            if self.client.start_matchmaking():
                self.matchmaking_started = True
            else:
                self.matchmaking_started = False
                print(f"[Matchmaking, {self.name}] Unable to start matchmaking.")

    def override_render(self):
        """Handles UI text rendering, including latency, player stats, and battle info."""
        latency_color = self.get_latency_color()
        latency_text = f"Latency: {int(average(self.latency))}ms"
        self.text_renderer.draw_text(latency_text, 20, 20, latency_color)

        # If in menu, show player info
        if self.scene_manager.current_scene == self.main_menu_scene:
            if self.client.state and self.client.state.menu_state:
                trophies_text = f"Trophies: {self.client.state.menu_state.trophies}"
                self.text_renderer.draw_text(trophies_text, 60, 190, (255, 255, 0))

                chest_text = f"Chests: {len(self.client.state.menu_state.chests)}"
                self.text_renderer.draw_text(chest_text, 60, 260, (200, 200, 200))

        # If in battle, show battle state
        elif self.scene_manager.current_scene == self.battle_scene:
            if self.client.state and self.client.state.battle_state:
                elixir_text = f"Elixir: {self.client.state.battle_state.elixir}"
                self.text_renderer.draw_text(elixir_text, 20, 80, (0, 255, 255))

                for i, card in enumerate(self.client.state.battle_state.hand):
                    if i < len(self.hand_buttons):
                        self.hand_buttons[i].text = card.name
                        self.hand_buttons[i].callback = partial(
                            self.card_pressed, self.client.state.battle_state.hand[i]
                        )

    def card_pressed(self, card: Card):
        print(card)
