from dataclasses import dataclass
import enum
from typing import List

from card import Card


class ChestRarity(enum.Enum):
    WOOD = 0,
    SILVER = 1,
    GOLD = 2,
    GIANT = 3,
    DEV = 4

@dataclass
class Chest:
    cards: List[Card]
    gold: int
    gems: int
    rarity: str 

def generate_chest(rarity: ChestRarity) -> Chest:
    match (rarity):
        case ChestRarity.WOOD:
            return Chest([], 0, 0, rarity.__str__())
        case ChestRarity.SILVER:
            return Chest([], 0, 0, rarity.__str__())
        case ChestRarity.GOLD:
            return Chest([], 0, 0, rarity.__str__())
        case ChestRarity.GIANT:
            return Chest([], 0, 0, rarity.__str__())
        case ChestRarity.DEV:
            return Chest([], 0, 0, rarity.__str__())
