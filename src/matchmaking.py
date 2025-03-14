import collections
from dataclasses import dataclass
from enum import Enum
from os import pardir
from socket import socket
import threading
import time
from typing import Callable, Dict, List, Optional, Tuple

from card import Card, Deck
from game_packet import MatchFound, MatchRequest, PacketType
from network import Packet
from uuid import uuid4
import random

from util import Mutex

MAX_TROPHY_DIFF = 100

@dataclass
class MatchRequestSocket:
    inner: MatchRequest
    sock: socket


@dataclass
class Player:
    uuid: str
    sock: socket
    hand: List[Card]
    next_card: Optional[Card]
    deck: Optional[Deck]
    remaining_in_deck: List[Card]
    elixir: int


@dataclass
class NetworkPlayer:
    uuid: str
    hand: List[Card]
    next_card: Optional[Card]
    deck: Optional[Deck]
    remaining_in_deck: List[Card]
    elixir: int


def network_player(p: Player) -> NetworkPlayer:
    return NetworkPlayer(
        p.uuid, p.hand, p.next_card, p.deck, p.remaining_in_deck, p.elixir
    )

class Owner(Enum):
    SELF = 0
    OTHER = 1

@dataclass 
class UnitData:
    x: int 
    y: int
    current_target: Optional["Unit"]
    hitpoints: int

@dataclass 
class Unit:
    underlying: Card
    owner: Owner
    unit_data: UnitData

@dataclass
class Battle:
    p1: Player
    p2: Player
    uuid: str
    units: List[Unit]


class MatchThread:
    MAX_ELIXIR = 10
    ELIXIR_TICK_TIME = 1

    def __init__(self, initial_state: Battle) -> None:
        self.thread = threading.Thread(target=self.loop, daemon=True)
        self.state = Mutex(initial_state)
        self.thread.start()

    def start(self) -> None:
        self.thread.start()

    def end(self) -> None:
        self.thread.join()

    def loop(self) -> None:
        while True:
            start_time = time.monotonic()
            self.tick()
            elapsed_time = time.monotonic() - start_time
            sleep_time = self.ELIXIR_TICK_TIME - elapsed_time
            if sleep_time > 0:
                time.sleep(sleep_time)

    def tick(self) -> None:
        state = self.state.get_data()

        if not state:
            return

        if state.p1.elixir < self.MAX_ELIXIR:
            state.p1.elixir += 1

        if state.p2.elixir < self.MAX_ELIXIR:
            state.p2.elixir += 1

        self.state.set_data(state)

    def get_state(self) -> Battle:
        data = self.state.get_data()
        if not data:
            raise ValueError("State Data is null")
        return data


class Matchmaking:
    def __init__(self) -> None:
        self.waiting: List[MatchRequestSocket] = []
        self.matches: Dict[str, MatchThread] = {}

    def request(self, d: MatchRequest, s: socket) -> None:
        for c in self.waiting:
            if c.inner.uuid == d.uuid:
                return

        for m in self.matches.values():
            if m.get_state().p1.uuid == d.uuid or m.get_state().p2.uuid == d.uuid:
                return

        # print(d)
        self.waiting.append(MatchRequestSocket(d, s))

    def tick(self, update_battle: Callable[[str, Optional[str]], None]) -> None:
        if len(self.waiting) < 2:
            return

        matched_pairs: List[Tuple[MatchRequestSocket, MatchRequestSocket]] = []
        i = 0
        while i < len(self.waiting):
            j = i + 1
            while j < len(self.waiting):
                if self.are_compatible(self.waiting[i].inner, self.waiting[j].inner):
                    matched_pairs.append((self.waiting[i], self.waiting[j]))
                    break
                j += 1
            i += 1

        for pair in matched_pairs:
            # print(pair[0], pair[1])
            i = self.handle_match(pair[0], pair[1])
            update_battle(pair[0].inner.uuid, i)
            update_battle(pair[1].inner.uuid, i)
            self.waiting.remove(pair[0])
            self.waiting.remove(pair[1])

    def get_match(
        self, uuid: str, player_uuid: str
    ) -> Tuple[Optional[NetworkPlayer], Optional[str]]:
        return next(
            (
                (
                    p,
                    (
                        m.get_state().p2.uuid
                        if p is m.get_state().p1
                        else m.get_state().p1.uuid
                    ),
                )
                for m in [self.matches.get(uuid)]
                if m
                for p in [
                    network_player(m.get_state().p1),
                    network_player(m.get_state().p2),
                ]
                if p.uuid == player_uuid
            ),
            (None, None),
        )

    def are_compatible(self, req1: MatchRequest, req2: MatchRequest) -> bool:
        trophy_difference = abs(req1.trophies - req2.trophies)
        return trophy_difference <= MAX_TROPHY_DIFF

    def handle_match(self, req1: MatchRequestSocket, req2: MatchRequestSocket) -> str:
        id = str(uuid4())
        p1_initial = random.sample(req1.inner.deck.cards, 4)
        p1_remaining = [
            item for item in req1.inner.deck.cards if item not in p1_initial
        ]
        random.shuffle(p1_remaining)
        p1_next = p1_remaining.pop()

        p2_initial = random.sample(req2.inner.deck.cards, 4)
        p2_remaining = [
            item for item in req2.inner.deck.cards if item not in p2_initial
        ]
        random.shuffle(p2_remaining)
        p2_next = p2_remaining.pop()

        self.matches.update(
            {
                id: MatchThread(
                    Battle(
                        Player(
                            req1.inner.uuid,
                            req1.sock,
                            p1_initial,
                            p1_next,
                            req1.inner.deck,
                            p1_remaining,
                            0,
                        ),
                        Player(
                            req2.inner.uuid,
                            req2.sock,
                            p2_initial,
                            p2_next,
                            req2.inner.deck,
                            p2_remaining,
                            0,
                        ),
                        id,
                        []
                    )
                ),
            }
        )

        req1.sock.sendall(
            Packet.from_struct(
                PacketType.MATCH_FOUND, MatchFound(id, req2.inner.uuid)
            ).serialize_with_length()
        )
        req2.sock.sendall(
            Packet.from_struct(
                PacketType.MATCH_FOUND, MatchFound(id, req1.inner.uuid)
            ).serialize_with_length()
        )

        return id
