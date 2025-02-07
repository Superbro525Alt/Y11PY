import logging


logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

from typing import Generic, TypeVar

T = TypeVar('T')
U = TypeVar('U')

class Pair(Generic[T, U]):
    """
    A simple class to represent a pair of values of potentially different types.
    """

    def __init__(self, first: T, second: U):
        self.first = first
        self.second = second

    def __repr__(self) -> str:
        return f"Pair<{self.first!r}, {self.second!r}>"  # Use !r for repr

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, Pair):  # Check type for equality
            return False
        return self.first == other.first and self.second == other.second

    def __hash__(self) -> int:
        return hash((self.first, self.second))  # Make it hashable

    def to_tuple(self) -> tuple[T, U]:
        return (self.first, self.second)

    @classmethod
    def from_tuple(cls, tup: tuple[T, U]) -> 'Pair[T, U]':
        if not isinstance(tup, tuple) or len(tup) != 2:
            raise TypeError("Input must be a tuple of length 2")
        return cls(tup[0], tup[1])
    
    def __iter__(self):
        yield self.first
        yield self.second
