from collections import deque
import enum
from functools import partial
import json
from logging import error, warn
import os
from random import randint, random
from socket import socket
from threading import Lock
from time import time
from types import SimpleNamespace
from typing import Callable, Deque, Dict, List, Optional, Tuple

from numpy import average
from copy import copy
from arena import Arena
from auth import DataRequest, LoginRequest, LoginResponse, ServerUserData, User, UserMap
from deck import Deck
from game_packet import MatchFound, MatchRequest, PacketType
from matchmaking import Matchmaking, UnitDeployRequest
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
from inspect import getsourcefile
from os.path import abspath
from dataclasses import dataclass
import datetime
from chest import Chest, ChestRarity, generate_chest
from clan import Clan
from shop import Shop, shop_default
from card import (
    ARCANE_CANNON,
    EARTHQUAKE,
    GOBLIN_SHAMAN,
    ICE_SPIKES,
    LUMBERJACK_GOBLIN,
    POISON_TOWER,
    ROCK_GOLEM,
    SKY_ARCHER,
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
    intersects,
)
from pipeline import Event, FramePipeline, StateData
from engine import Engine
from unit import Owner
from util import json_to_dataclass, logger


@dataclass
class BattleState:
    elixir: int
    hand: List[Card]
    next: Optional[Card]
    match_uuid: str
    other_uuid: str
    arena: Arena


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
    def __init__(self, send: Callable[[Packet], None]) -> None:
        self.battle_state: Optional[BattleState] = None
        self.send = send

    def tick(self, state: Optional[GameState]) -> None:
        if state and state.battle_state:
            self.battle_state = state.battle_state

    def place_unit(self, card: Card, location: Tuple[int, int], id: str) -> None:
        if self.battle_state and self.battle_state.elixir >= card.elixir_cost:
            self.send(
                Packet.from_struct(
                    PacketType.DEPLOY_UNIT,
                    UnitDeployRequest(location, card, id, self.battle_state.match_uuid),
                )
            )


class GameNetworkClient(Client):
    def __init__(self, name: str, ip: Optional[str], on_finish: Optional[Callable[[], None]]):
        super().__init__(ip if ip else "127.0.0.1", 12345)

        self.battle_client = BattleClient(self.send)

        self.state_lock = Lock()
        self.status_lock = Lock()
        self.connection_status_lock = Lock()

        self.state: Optional[GameState] = None
        self.status: Optional[ServerStatus] = ServerStatus()
        self.connection_status: ConnectionStatus = ConnectionStatus(None, False)
        self.auth_state: AuthState = AuthState(False, None, False, None)
        self.name = name
        self.side: Optional[str] = None

        self.on_finish = on_finish

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
                logger.error(f"Server Connection Error: {e}")
                # print("e")
                # raise ValueError(
                #     f"Transmitted Game State was in an invalid format: {e}"
                # )
                pass

            self.battle_client.tick(self.state)

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
        do_if(packet, PacketType.MATCH_END, lambda: self.on_finish() if self.on_finish is not None else None)

    def found_match(self, packet: Packet):
        m: MatchFound = MatchFound(**json.loads(packet.data.decode()))

        self.side = m.p

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

    def deploy_unit(self, card: Card, pos: Tuple[int, int]) -> None:
        if (
            self.auth_state
            and self.auth_state.uuid
            and self.state
            and self.state.battle_state
        ):
            self.battle_client.place_unit(card, pos, self.auth_state.uuid)

    def buy_card(self, card: Card):
        pass


class NetworkStateObject(NetworkObject):
    def __init__(self):
        super().__init__()
        self._handles = [
            PacketType.LOGIN,
            PacketType.CLIENT_SERVER_SYNC,
            PacketType.MATCH_REQUEST,
            PacketType.DEPLOY_UNIT,
            PacketType.SHOP_PURCHASE
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
        self.shop = shop_default()
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
                    found_match, other_uuid, arena = self.matchmaking.get_match(
                        found.data.current_battle, data.uuid
                    )

                    if found_match and other_uuid and arena:
                        state.battle_state = BattleState(
                            found_match.elixir,
                            found_match.hand,
                            found_match.next_card,
                            found.data.current_battle,
                            other_uuid,
                            arena,
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
        elif packet.packet_type == PacketType.DEPLOY_UNIT:
            data = json.loads(
                packet.data.decode(), object_hook=lambda d: SimpleNamespace(**d)
            )

            self.matchmaking.deploy_unit(data, data.battle_id)
        elif packet.packet_type == PacketType.SHOP_PURCHASE:
            pass

    def tick(self):
        self.matchmaking.tick(
            lambda user_id, battle_id: self.users.update_battle(user_id, battle_id), self.users.update_trophies
        )


class GameServer(Server):
    def __init__(self) -> None:
        super().__init__(12345, [NetworkStateObject()])

    def tick(self) -> None:
        pass


class Game(Engine):
    HAND_INITIAL_COLOR = (99, 99, 99)
    HAND_SELECTED_COLOR = (255, 79, 79)

    def __init__(self, name: str, ip: Optional[str] = None):
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
        self.client = GameNetworkClient(self.name, ip, on_finish=self.stop_matchmaking)
        self.matchmaking_started = False  # To track matchmaking state

        self.latency: Deque[int] = deque([0], maxlen=10)  # Track server latency
        self.ui_buttons = []

        # Register scenes
        self.main_menu_scene = Scene("main_menu")
        self.battle_scene = Scene("battle")

        self.selected_card: Optional[Card] = None

        self.chest_buttons: List[UIButton] = []

    def stop_matchmaking(self) -> None:
        self.matchmaking_started = False

    def setup_scenes(self):
        """Initializes all scenes and UI elements."""

        # Latency Display (Present in All Scenes)
        self.latency_display = UIElement(20, 20, 200, 30, color=(50, 50, 50))
        self.main_menu_scene.add_ui_element(self.latency_display)
        self.battle_scene.add_ui_element(self.latency_display)

        self.main_menu_bg = UIElement(
            0,
            0,
            self.sdl.get_width(),
            self.sdl.get_height(),
            color=(32, 67, 118),  # Clash Royale Blue
        )
        self.main_menu_scene.add_ui_element(self.main_menu_bg)

        # Title Banner (Gold Clash Royale Aesthetic)
        title_banner = UIElement(
            int(self.sdl.get_width() / 6),
            50,
            int(self.sdl.get_width() - self.sdl.get_width() / 6 * 2),
            100,
            color=(255, 215, 0),
        )
        self.main_menu_scene.add_ui_element(title_banner)

        # Player Trophy Display (Styled Like Clash Royale)
        self.trophy_display = UIElement(50, 180, 200, 50, color=(200, 170, 0))
        self.main_menu_scene.add_ui_element(self.trophy_display)

        # Chest Info (4 chests at the bottom, like Clash Royale)
        # if self.client.state and self.client.state.menu_state:
        chest_positions = [
            (
                self.sdl.get_width() // 2 - ((4 * 170) // 2) + i * 170,
                self.sdl.get_height() - 150,
            )
            for i in range(4)
        ]
        self.chest_buttons = []
        for i, pos in enumerate(chest_positions):
            chest_button = UIButton(
                pos[0],
                pos[1],
                150,
                100,
                self.text_renderer,
                text=f"Chest {i+1}",
                color=(100, 75, 50),
                on_hover=(150, 120, 90),
            )
            self.chest_buttons.append(chest_button)
            self.main_menu_scene.add_ui_element(chest_button)

        # **🏆 Matchmaking Button (Styled)**
        start_button = UIButton(
            (self.sdl.get_width() - 200) // 2,
            350,
            200,
            90,
            self.text_renderer,
            color=(0, 200, 0),
            on_hover=(0, 255, 0),
            callback=self.start_matchmaking,
            text="Battle",
        )
        self.main_menu_scene.add_ui_element(start_button)

        # **🛒 Shop Button (Styled)**
        shop_button = UIButton(
            (self.sdl.get_width() - 200) // 2 - 250,
            350,
            200,
            80,
            self.text_renderer,
            color=(50, 50, 255),
            on_hover=(80, 80, 255),
            callback=self.open_shop,
            text="Shop",
        )
        self.main_menu_scene.add_ui_element(shop_button)

        # **📜 Deck Management Button (Styled)**
        deck_button = UIButton(
            (self.sdl.get_width() - 200) // 2 + 250,
            350,
            200,
            80,
            self.text_renderer,
            color=(255, 50, 50),
            on_hover=(255, 80, 80),
            callback=self.open_deck_management,
            text="Decks",
        )
        self.main_menu_scene.add_ui_element(deck_button)

        # Register Scenes
        self.setup_shop_scene()
        self.setup_deck_management_scene()

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

        self.player_display = UIElement(
            20,  # Center horizontally
            140,  # Near the bottom
            100,  # Wider
            30,
            color=(0, 0, 255),
        )

        self.battle_scene.add_ui_element(self.player_display)

        self.battle_scene.add_ui_element(self.elixir_display)

        # Spreading Hand Cards More Evenly Across the Bottom
        self.hand_buttons = []
        hand_card_width = self.text_renderer.get_text_width("aaaaaaaaaaaaaaaa") + 10
        hand_card_height = self.text_renderer.get_font_height("Card") + 10
        spacing = 20
        hand_start_x = (self.sdl.get_width() - (hand_card_width * 4 + spacing * 3)) // 2
        hand_y = self.sdl.get_height() - 80

        for i in range(4):  # Assuming a 4-card hand
            card_x = hand_start_x + i * (hand_card_width + spacing)

            card_button = UIButton(
                card_x,
                hand_y,
                hand_card_width,
                hand_card_height,
                self.text_renderer,
                color=self.HAND_INITIAL_COLOR,
                on_hover=(69, 69, 69),  # Add slight transparency on hover
                callback=None,
                text="Card",
            )
            self.battle_scene.add_ui_element(card_button)
            self.hand_buttons.append(card_button)

        self.input_manager.register_mouse_down(self.mouse_down)

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
            and self.client.state.battle_state is None
            and self.scene_manager.current_scene is not None
            and self.scene_manager.current_scene == "battle"
        ):
            self.go_to_main_menu()

    def setup_shop_scene(self):
        """Creates the improved Clash Royale styled shop UI scene."""
        self.shop_scene = Scene("shop")

        # Background
        self.shop_bg = UIElement(
            0, 0, self.sdl.get_width(), self.sdl.get_height(), color=(32, 67, 118)
        )
        self.shop_scene.add_ui_element(self.shop_bg)

        # Shop Title Banner
        shop_title = UIElement(
            (self.sdl.get_width() - 400) // 2, 50, 400, 80, color=(255, 215, 0)
        )
        self.shop_scene.add_ui_element(shop_title)

        # Display available cards for purchase
        self.shop_items = {"Goblin": 100, "Knight": 200, "Archer": 150, "Wizard": 300}
        card_width, card_height = 180, 220
        spacing = 20
        total_width = (
            len(self.shop_items) * card_width + (len(self.shop_items) - 1) * spacing
        )
        start_x = (self.sdl.get_width() - total_width) // 2
        y_offset = 180

        for i, (card, price) in enumerate(self.shop_items.items()):
            card_x = start_x + i * (card_width + spacing)
            buy_card_button = UIButton(
                card_x,
                y_offset,
                card_width,
                card_height,
                self.text_renderer,
                text=f"{card} - {price} Coins",
                color=(0, 200, 200),
                on_hover=(0, 255, 255),
                callback=lambda c=card: self.buy_card(c),
            )
            self.shop_scene.add_ui_element(buy_card_button)

        # Back button
        back_button = UIButton(
            50,
            self.sdl.get_height() - 100,
            150,
            70,
            self.text_renderer,
            text="Back",
            color=(200, 0, 0),
            on_hover=(255, 50, 50),
            callback=self.go_to_main_menu,
        )
        self.shop_scene.add_ui_element(back_button)

        self.scene_manager.add_scene(self.shop_scene)

    def setup_deck_management_scene(self):
        """Creates the Clash Royale styled deck management UI scene."""
        self.deck_management_scene = Scene("deck_management")

        # Background
        self.deck_bg = UIElement(
            0, 0, self.sdl.get_width(), self.sdl.get_height(), color=(32, 67, 118)
        )
        self.deck_management_scene.add_ui_element(self.deck_bg)

        # Deck selection (5 deck buttons at the top)
        self.selected_deck = 0
        deck_count = 5
        deck_width = 120
        deck_height = 70
        deck_spacing = 30
        total_width = deck_count * deck_width + (deck_count - 1) * deck_spacing
        start_x = (self.sdl.get_width() - total_width) // 2
        deck_y = 50

        self.deck_buttons = []
        for i in range(deck_count):
            deck_x = start_x + i * (deck_width + deck_spacing)
            deck_button = UIButton(
                deck_x,
                deck_y,
                deck_width,
                deck_height,
                self.text_renderer,
                text=f"Deck {i+1}",
                color=(200, 100, 100),
                on_hover=(255, 120, 120),
                callback=lambda i=i: self.select_deck(i),
            )
            self.deck_buttons.append(deck_button)
            self.deck_management_scene.add_ui_element(deck_button)

        # Back button
        back_button = UIButton(
            50,
            self.sdl.get_height() - 100,
            150,
            70,
            self.text_renderer,
            text="Back",
            color=(200, 0, 0),
            on_hover=(255, 50, 50),
            callback=self.go_to_main_menu,
        )
        self.deck_management_scene.add_ui_element(back_button)

        self.scene_manager.add_scene(self.deck_management_scene)

    def open_shop(self):
        self.scene_manager.load_scene("shop")

    def open_deck_management(self):
        self.scene_manager.load_scene("deck_management")

    def buy_chest(self):
        print("[SHOP] Chest Purchased!")

    def select_deck(self, deck_index):
        self.selected_deck = deck_index
        print(f"[DECK] Deck {deck_index + 1} Selected!")

    def buy_card(self, card_name):
        print(f"[SHOP] {card_name} Purchased!")

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
            os.path.dirname(os.path.abspath(__file__)) + "/SourceSansPro-Regular.otf", 24
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

                for i, button in enumerate(self.chest_buttons):
                    if len(self.client.state.menu_state.chests) > i:
                        button.text = str(
                            ChestRarity.from_val(
                                self.client.state.menu_state.chests[i].rarity
                            )
                        )
        # If in battle, show battle state
        elif self.scene_manager.current_scene == self.battle_scene:
            if self.client.state and self.client.state.battle_state:
                elixir_text = f"Elixir: {self.client.state.battle_state.elixir}"
                self.text_renderer.draw_text(elixir_text, 20, 80, (0, 255, 255))
                self.text_renderer.draw_text(
                    f"{self.client.side}", 20, 140, (255, 255, 255)
                )

                for i, card in enumerate(self.client.state.battle_state.hand):
                    if i < len(self.hand_buttons):
                        self.hand_buttons[i].text = card.name
                        temp = self.hand_buttons.copy()
                        temp.remove(self.hand_buttons[i])
                        self.hand_buttons[i].callback = partial(
                            self.card_pressed,
                            self.client.state.battle_state.hand[i],
                            self.hand_buttons[i],
                            temp,
                        )

                # Draw arena grid
                if self.client.state.battle_state.arena:  # PLAYER 2 IS FURTHEST
                    arena = self.client.state.battle_state.arena
                    cell_size = 20  # Adjust as needed
                    offset_x = int(
                        (self.sdl.get_width() / 2) - ((cell_size * Arena.WIDTH) / 2)
                    )
                    offset_y = int(380 - ((cell_size * Arena.HEIGHT) / 2))

                    tile_colors = {
                        0: (99, 99, 99),  # EMPTY
                        1: (0, 100, 255),  # RIVER
                        2: (139, 69, 20),  # BRIDGE
                        3: (255, 0, 0),  # CROWN_TOWER
                        4: (255, 215, 0),  # KING_TOWER
                    }

                    for y in range(Arena.HEIGHT):
                        for x in range(Arena.WIDTH):
                            tile_type = arena.tiles[y][x]
                            color: Tuple[int, int, int] = tile_colors.get(
                                tile_type, (0, 0, 0)
                            )
                            rect = (
                                offset_x + x * cell_size,
                                offset_y + y * cell_size,
                                cell_size,
                                cell_size,
                            )
                            if (
                                (
                                    Arena.get_tile_owner((x, y)) == Owner.P1
                                    and self.client.side != "Player 1"
                                )
                                or (
                                    Arena.get_tile_owner((x, y)) == Owner.P2
                                    and self.client.side != "Player 2"
                                )
                                or Arena.get_tile_owner((x, y)) == None
                            ):
                                color = (color[0] - 20, color[1] - 20, color[2] - 20)
                                if color[2] < 0:
                                    color = (color[0], color[1], 0)
                                if color[1] < 0:
                                    color = (color[0], 0, color[2])
                                if color[0] < 0:
                                    color = (0, color[1], color[2])

                            if tile_type not in (3, 4):
                                self.sdl.fill_rect(
                                    rect[0],
                                    rect[1],
                                    rect[2],
                                    rect[3],
                                    color[0],
                                    color[1],
                                    color[2],
                                )
                            else:
                                if not Arena.is_tower_dead(arena, x, y):
                                    self.sdl.fill_rect(
                                        rect[0],
                                        rect[1],
                                        rect[2],
                                        rect[3],
                                        color[0],
                                        color[1],
                                        color[2],
                                    )
                                else:
                                    color = tile_colors[0]
                                    if (
                                        (
                                            Arena.get_tile_owner((x, y)) == Owner.P1
                                            and self.client.side != "Player 1"
                                        )
                                        or (
                                            Arena.get_tile_owner((x, y)) == Owner.P2
                                            and self.client.side != "Player 2"
                                        )
                                        or Arena.get_tile_owner((x, y)) == None
                                    ):
                                        color = (
                                            color[0] - 20,
                                            color[1] - 20,
                                            color[2] - 20,
                                        )
                                        if color[2] < 0:
                                            color = (color[0], color[1], 0)
                                        if color[1] < 0:
                                            color = (color[0], 0, color[2])
                                        if color[0] < 0:
                                            color = (0, color[1], color[2])

                                    self.sdl.fill_rect(
                                        rect[0],
                                        rect[1],
                                        rect[2],
                                        rect[3],
                                        color[0],
                                        color[1],
                                        color[2],
                                    )

                            self.sdl.draw_rect(
                                rect[0], rect[1], rect[2], rect[3], 255, 255, 255
                            )  # Add outline

                            if tile_type in (3, 4) and not Arena.is_tower_dead(
                                arena, x, y
                            ):  # Crown or King Tower
                                for tower in arena.towers:
                                    if tower.center_x == x and tower.center_y == y:
                                        hp_bar_width = cell_size * 0.8
                                        hp_bar_height = cell_size / 5
                                        hp_bar_x = (
                                            rect[0] + (cell_size - hp_bar_width) / 2
                                        )
                                        hp_bar_y = rect[1] + hp_bar_height - 2

                                        # Calculate HP percentage
                                        hp_percentage = (
                                            tower.current_hp / tower.max_hp
                                            if tower.max_hp > 0
                                            else 0
                                        )
                                        filled_width = int(hp_bar_width * hp_percentage)

                                        self.sdl.fill_rect(
                                            int(hp_bar_x),
                                            int(hp_bar_y),
                                            int(hp_bar_width),
                                            int(hp_bar_height),
                                            0,
                                            0,
                                            0,
                                        )

                                        hp_color = (
                                            (0, 255, 0)
                                            if hp_percentage > 0.5
                                            else (
                                                (255, 255, 0)
                                                if hp_percentage > 0.2
                                                else (255, 0, 0)
                                            )
                                        )

                                        self.sdl.fill_rect(
                                            int(hp_bar_x),
                                            int(hp_bar_y),
                                            filled_width,
                                            int(hp_bar_height),
                                            hp_color[0],
                                            hp_color[1],
                                            hp_color[2],
                                        )

                    # Draw units
                    if arena.units and self.client.side:
                        for unit in arena.units:
                            unit_x = offset_x + unit.inner.unit_data.x * cell_size
                            unit_y = offset_y + unit.inner.unit_data.y * cell_size
                            unit_rect = (unit_x, unit_y, cell_size, cell_size)
                            if (
                                unit.inner.owner == Owner.P1.value
                                and self.client.side == "Player 1"
                            ) or (
                                unit.inner.owner == Owner.P2.value
                                and self.client.side == "Player 2"
                            ):
                                self.sdl.fill_rect(
                                    unit_rect[0],
                                    unit_rect[1],
                                    unit_rect[2],
                                    unit_rect[3],
                                    0,
                                    100,
                                    0,
                                )  # Draw units in green
                            else:
                                self.sdl.fill_rect(
                                    unit_rect[0],
                                    unit_rect[1],
                                    unit_rect[2],
                                    unit_rect[3],
                                    100,
                                    0,
                                    0,
                                )  # Draw units in red
                            self.sdl.draw_rect(
                                unit_rect[0],
                                unit_rect[1],
                                unit_rect[2],
                                unit_rect[3],
                                0,
                                0,
                                0,
                            )  # Add outline

                            if (
                                unit.inner.unit_data.hitpoints
                                and unit.inner.underlying.hitpoints
                            ):
                                self.sdl.fill_rect(
                                    int(unit_x + (cell_size / 5)),
                                    int(unit_y + (cell_size / 5)),
                                    int(
                                        # cell_size
                                        # - ((cell_size / 5) * 2)
                                        (
                                            (
                                                unit.inner.unit_data.hitpoints
                                                / unit.inner.underlying.hitpoints
                                            )
                                            * ((cell_size / 5) * 3)
                                        )
                                    ),
                                    int(cell_size - ((cell_size / 5) * 2)),
                                    0,
                                    255,
                                    0,
                                )
                                self.sdl.draw_rect(
                                    int(unit_x + (cell_size / 5)),
                                    int(unit_y + (cell_size / 5)),
                                    int(cell_size - ((cell_size / 5) * 2)),
                                    int(cell_size - ((cell_size / 5) * 2)),
                                    0,
                                    0,
                                    0,
                                )

    def card_pressed(self, card: Card, button: UIButton, other_buttons: List[UIButton]):
        self.selected_card = card
        button.color = self.HAND_SELECTED_COLOR
        for b in other_buttons:
            b.color = self.HAND_INITIAL_COLOR

    def mouse_down(self, pos: Tuple[int, int]) -> None:
        if (
            self.scene_manager.current_scene
            and self.scene_manager.current_scene.name == "battle"
        ):
            cell_size = 20
            offset_x = int((self.sdl.get_width() / 2) - ((cell_size * Arena.WIDTH) / 2))
            offset_y = int(380 - ((cell_size * Arena.HEIGHT) / 2))

            grid_x = (pos[0] - offset_x) // cell_size
            grid_y = (pos[1] - offset_y) // cell_size

            if (
                0 <= grid_x < Arena.WIDTH
                and 0 <= grid_y < Arena.HEIGHT
                and self.selected_card
            ):
                self.client.deploy_unit(self.selected_card, (grid_x, grid_y))
                self.selected_card = None
                for b in self.hand_buttons:
                    b.color = self.HAND_INITIAL_COLOR
