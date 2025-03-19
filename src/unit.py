from dataclasses import dataclass
from enum import Enum
from socket import socket
from typing import List, Optional, Self, Tuple
from uuid import uuid4

from card import Card
from deck import Deck 

from datetime import datetime

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
    P1 = 0
    P2 = 1

class UnitTargetType(Enum):
    KING_TOWER = 0 
    PRINCESS_TOWER = 1
    TROOP = 2
    BUILDING = 3

@dataclass 
class UnitTarget:
    uuid: str
    unit_type: UnitTargetType
    path: List[Tuple[int, int]]

@dataclass
class UnitData:
    x: int
    y: int
    current_target: Optional[UnitTarget]
    hitpoints: int
    last_move: str
    last_attack: str

@dataclass
class Unit:
    underlying: Card
    owner: Owner
    unit_data: UnitData


@dataclass
class IDUnit:
    inner: Unit
    id: str

    @classmethod
    def from_unit(cls, unit: Unit) -> Self:
        return cls(unit, str(uuid4()))


@dataclass
class UnitDeployRequest:
    pos: Tuple[int, int]
    card: Card
    owner: str
    battle_id: str


@dataclass
class Battle:
    p1: Player
    p2: Player
    uuid: str
    units: List[IDUnit]

