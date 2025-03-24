from dataclasses import dataclass
import enum
from typing import Generic, List, Optional, Self, Type, TypeVar

from card import Card

T = TypeVar("T", bound="EnumFromValue")


class EnumFromValue(enum.Enum):
    @classmethod
    def from_val(cls: Type["EnumFromValue"], value) -> Optional["EnumFromValue"]:
        for member in cls:
            if member.value == value:
                return member
        return None


class ChestRarity(EnumFromValue):
    WOOD = 0
    SILVER = 1
    GOLD = 2
    GIANT = 3
    DEV = 4

    @classmethod
    def from_val(cls, value) -> Optional["EnumFromValue"]:
        return super().from_val(value)

    def __str__(self) -> str:
        match self.value:
            case self.WOOD.value:
                return "Wood"
            case self.SILVER.value:
                return "Silver"
            case self.GOLD.value:
                return "Gold"
            case self.GIANT.value:
                return "Giant"
            case self.DEV.value:
                return "Dev"


@dataclass
class Chest:
    cards: List[Card]
    gold: int
    gems: int
    rarity: ChestRarity


def generate_chest(rarity: ChestRarity) -> Chest:
    match (rarity):
        case ChestRarity.WOOD:
            return Chest([], 0, 0, rarity)
        case ChestRarity.SILVER:
            return Chest([], 0, 0, rarity)
        case ChestRarity.GOLD:
            return Chest([], 0, 0, rarity)
        case ChestRarity.GIANT:
            return Chest([], 0, 0, rarity)
        case ChestRarity.DEV:
            return Chest([], 0, 0, rarity)
