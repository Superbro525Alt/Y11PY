import logging
import json
from dataclasses import dataclass, field
from threading import Lock
import threading
from typing import Callable, Optional, List, Dict, Any, Tuple, Union

from chest import ChestRarity

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

from typing import Generic, TypeVar
import math

T = TypeVar("T")
U = TypeVar("U")


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
    def from_tuple(cls, tup: tuple[T, U]) -> "Pair[T, U]":
        if not isinstance(tup, tuple) or len(tup) != 2:
            raise TypeError("Input must be a tuple of length 2")
        return cls(tup[0], tup[1])

    def __iter__(self):
        yield self.first
        yield self.second


def is_point_inside_circle(
    center_x: float, center_y: float, radius: float, point_x: float, point_y: float
):
    """
    Checks if a point is inside a circle.

    Args:
        center_x: The x-coordinate of the circle's center.
        center_y: The y-coordinate of the circle's center.
        radius: The radius of the circle.
        point_x: The x-coordinate of the point to check.
        point_y: The y-coordinate of the point to check.

    Returns:
        True if the point is inside or on the circle, False otherwise.
    """

    distance = math.sqrt((point_x - center_x) ** 2 + (point_y - center_y) ** 2)

    return distance <= radius


def json_to_dataclass(data: bytes, root_dataclass_name: str = "GameState") -> Any:
    """
    Converts a JSON byte string into a nested dataclass structure.
    """
    json_data = json.loads(data.decode())
    dataclass_definitions = {}

    def _create_dataclass(name: str, data: Union[Dict[str, Any], List[Any]]) -> type:
        """
        Recursively creates dataclass definitions from a JSON dictionary or list of dictionaries.
        """
        if name in dataclass_definitions:
            return dataclass_definitions[name]

        if (
            isinstance(data, list) and data and isinstance(data[0], dict)
        ):  # list of dictionaries
            sub_dataclass_name = "".join(
                word.capitalize() for word in name.split("_singular")
            )
            if not sub_dataclass_name:
                sub_dataclass_name = "".join(
                    word.capitalize() for word in name.split("_")
                )
            sub_dataclass = _create_dataclass(sub_dataclass_name, data[0])
            return List[sub_dataclass]

        if isinstance(data, list):
            if data and isinstance(data[0], (int, float, str, bool)):
                return List[type(data[0])]
            else:
                return List[Any]

        if not isinstance(data, dict):  # primitive types
            return type(data)

        fields = []
        annotations = {}

        for key, value in data.items():
            field_type = type(value)

            if isinstance(value, dict) or isinstance(value, list):
                sub_dataclass_name = "".join(
                    word.capitalize() for word in key.split("_")
                )
                field_type = _create_dataclass(sub_dataclass_name, value)
            else:
                if key == "rarity":
                    field_type = ChestRarity
                else:
                    field_type = type(value)

            fields.append((key, field(default=None)))
            annotations[key] = Optional[field_type]

        new_dataclass = dataclass(type(name, (), {"__annotations__": annotations}))
        dataclass_definitions[name] = new_dataclass
        return new_dataclass

    root_dataclass = _create_dataclass(root_dataclass_name, json_data)
    return root_dataclass(**json_data)

T = TypeVar('T')

class Mutex(Generic[T]):
    """
    A mutex that holds data, with mutable and immutable access.
    """

    def __init__(self, data: Optional[T] = None):
        self._lock = threading.Lock()
        self._data = data

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        """Acquires the lock."""
        return self._lock.acquire(blocking, timeout)

    def release(self) -> None:
        """Releases the lock."""
        self._lock.release()

    def get_data(self) -> Optional[T]:
        """Gets the data immutably (read-only)."""
        with self._lock:
            return self._data

    def get_mutable_data(self) -> Optional[Tuple[threading.Lock, Optional[T]]]:
        """Gets the data mutably (with lock). Returns the lock and data, or None if lock fails."""
        if self.acquire():
            return self._lock, self._data
        else:
            return None

    def set_data(self, new_data: T) -> None:
        """Sets the data (requires lock)."""
        with self._lock:
            self._data = new_data

    def __enter__(self) -> 'Mutex[T]':
        """Context manager enter method."""
        self.acquire()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit method."""
        self.release()
