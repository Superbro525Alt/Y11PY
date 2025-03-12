from dataclasses import dataclass
from socket import socket
from typing import Dict, List, Optional, Tuple

from card import Card
from game_packet import MatchFound, MatchRequest, PacketType
from network import Packet
from uuid import uuid4

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
    elixir: int


@dataclass
class Battle:
    p1: Player
    p2: Player
    uuid: str


class Matchmaking:
    def __init__(self) -> None:
        self.waiting: List[MatchRequestSocket] = []
        self.matches: Dict[str, Battle] = {}

    def request(self, d: MatchRequest, s: socket) -> None:
        for c in self.waiting:
            if c.inner.uuid == d.uuid:
                return

        for m in self.matches.values():
            if m.p1.uuid == d.uuid or m.p2.uuid == d.uuid:
                return

        self.waiting.append(MatchRequestSocket(d, s))

    def tick(self) -> None:
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
            self.handle_match(pair[0], pair[1])
            self.waiting.remove(pair[0])
            self.waiting.remove(pair[1])

    def get_match(
        self, uuid: str, player_uuid: str
    ) -> Tuple[Optional[Player], Optional[str]]:
        return next(
            (
                (p, m.p2.uuid if p is m.p1 else m.p1.uuid)
                for m in [self.matches.get(uuid)]
                if m
                for p in [m.p1, m.p2]
                if p.uuid == player_uuid
            ),
            (None, None),
        )

    def are_compatible(self, req1: MatchRequest, req2: MatchRequest) -> bool:
        trophy_difference = abs(req1.trophies - req2.trophies)
        return trophy_difference <= MAX_TROPHY_DIFF

    def handle_match(self, req1: MatchRequestSocket, req2: MatchRequestSocket) -> None:
        id = str(uuid4())
        self.matches.update(
            {
                id: Battle(
                    Player(req1.inner.uuid, req1.sock, [], None, 0),
                    Player(req2.inner.uuid, req2.sock, [], None, 0),
                    id,
                )
            }
        )
        print(str(self.matches))
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
