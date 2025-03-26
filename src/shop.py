from dataclasses import dataclass
from typing import List

from card import GOBLIN_DRILL, TIME_WIZARD, Card


@dataclass
class ShopCard:
    card: Card
    price: int

@dataclass
class Shop:
    cards: List[ShopCard]

def shop_default() -> Shop:
    return Shop(cards=[ShopCard(TIME_WIZARD, 100), ShopCard(GOBLIN_DRILL, 100)])
