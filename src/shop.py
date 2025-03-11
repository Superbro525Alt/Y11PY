from dataclasses import dataclass
from typing import List

from card import Card

@dataclass 
class ShopCard:
    card: Card
    price: int

@dataclass 
class Shop:
    cards: List[ShopCard]
