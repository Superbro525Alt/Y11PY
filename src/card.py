from dataclasses import dataclass
from typing import List


class Card:
    pass

@dataclass 
class Deck:
    cards: List[Card]
