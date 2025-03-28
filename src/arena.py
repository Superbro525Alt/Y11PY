from copy import copy
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
import heapq
from typing import Dict, List, Optional, Self, Tuple

from card import CardType, TargetType
from unit import IDUnit, Owner, UnitTarget, UnitTargetType
from util import DATE_FORMAT, is_time_elapsed
from util import logger as logging

KING_MAX_HP = 1000
PRINCESS_MAX_HP = 500


class TileType(Enum):
    EMPTY = 0  # Walkable tile
    RIVER = 1  # Water (unwalkable)
    BRIDGE = 2  # Bridge over river
    CROWN_TOWER = 3  # Crown Tower (3x3 structure)
    KING_TOWER = 4  # King Tower (3x3 structure)


@dataclass
class Tower:
    tower_type: UnitTargetType
    center_x: int
    center_y: int
    owner: Owner
    tower_id: "TowerId"
    max_hp: int
    current_hp: int


class TowerId(Enum):
    PRINCESS_LEFT_P1 = "PRINCESS_LEFT_P1"
    PRINCESS_RIGHT_P1 = "PRINCESS_RIGHT_P1"
    KING_P1 = "KING_P1"

    PRINCESS_LEFT_P2 = "PRINCESS_LEFT_P2"
    PRINCESS_RIGHT_P2 = "PRINCESS_RIGHT_P2"
    KING_P2 = "KING_P2"


class Arena:
    WIDTH: int = 19
    HEIGHT: int = 30

    def __init__(self) -> None:
        self.tiles = [
            [TileType.EMPTY.value for _ in range(self.WIDTH)]
            for _ in range(self.HEIGHT)
        ]

        for x in range(self.WIDTH):
            self.tiles[self.HEIGHT // 2 - 1][x] = TileType.RIVER.value
            self.tiles[self.HEIGHT // 2][x] = TileType.RIVER.value

        for dy in range(2):
            self.tiles[self.HEIGHT // 2 - 1 + dy][3] = TileType.BRIDGE.value
            self.tiles[self.HEIGHT // 2 - 1 + dy][15] = TileType.BRIDGE.value

        king_x = self.WIDTH // 2
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                self.tiles[2 + dy][
                    king_x + dx
                ] = TileType.KING_TOWER.value  # Move forward
                self.tiles[self.HEIGHT - 3 + dy][
                    king_x + dx
                ] = TileType.KING_TOWER.value

        crown_positions = [
            (3, 3),
            (3, self.WIDTH - 4),
            (self.HEIGHT - 4, 3),
            (self.HEIGHT - 4, self.WIDTH - 4),
        ]
        for y, x in crown_positions:
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    self.tiles[y + dy][
                        x + dx
                    ] = TileType.CROWN_TOWER.value  # Move forward

        self.units: List[IDUnit] = []

        self.towers: List[Tower] = [
            Tower(
                UnitTargetType.KING_TOWER,
                self.WIDTH // 2,
                2,
                Owner.P1,
                TowerId.KING_P1,
                KING_MAX_HP,
                KING_MAX_HP,
            ),
            Tower(
                UnitTargetType.KING_TOWER,
                self.WIDTH // 2,
                self.HEIGHT - 3,
                Owner.P2,
                TowerId.KING_P2,
                KING_MAX_HP,
                KING_MAX_HP,
            ),
            Tower(
                UnitTargetType.PRINCESS_TOWER,
                3,
                3,
                Owner.P1,
                TowerId.PRINCESS_LEFT_P1,
                PRINCESS_MAX_HP,
                PRINCESS_MAX_HP,
            ),
            Tower(
                UnitTargetType.PRINCESS_TOWER,
                self.WIDTH - 4,
                3,
                Owner.P1,
                TowerId.PRINCESS_RIGHT_P1,
                PRINCESS_MAX_HP,
                PRINCESS_MAX_HP,
            ),
            Tower(
                UnitTargetType.PRINCESS_TOWER,
                3,
                self.HEIGHT - 4,
                Owner.P2,
                TowerId.PRINCESS_LEFT_P2,
                PRINCESS_MAX_HP,
                PRINCESS_MAX_HP,
            ),
            Tower(
                UnitTargetType.PRINCESS_TOWER,
                self.WIDTH - 4,
                self.HEIGHT - 4,
                Owner.P2,
                TowerId.PRINCESS_RIGHT_P2,
                PRINCESS_MAX_HP,
                PRINCESS_MAX_HP,
            ),
        ]

        self._set_tower_tiles()

    def _set_tower_tiles(self) -> None:
        t = copy(self.tiles.copy())

        for y in range(self.HEIGHT):
            for x in range(self.WIDTH):
                if self.tiles[y][x] in {3, 4}:
                    t[y][x] = 0
        for tower in self.towers:
            if tower.tower_type == UnitTargetType.KING_TOWER:
                for dx in range(-1, 2):
                    for dy in range(-1, 2):
                        t[tower.center_y + dy][
                            tower.center_x + dx
                        ] = TileType.KING_TOWER.value
            elif tower.tower_type == UnitTargetType.PRINCESS_TOWER:
                for dx in range(-1, 2):
                    for dy in range(-1, 2):
                        t[tower.center_y + dy][
                            tower.center_x + dx
                        ] = TileType.CROWN_TOWER.value

        # self.tiles = t.copy()

    def has_won(self, owner: Owner) -> bool:
        """Checks if the given owner has won the game."""
        opponent = Owner.P2 if owner == Owner.P1 else Owner.P1
        return any(tower.current_hp <= 0 for tower in self.towers if tower.owner == opponent and tower.tower_type == UnitTargetType.KING_TOWER)

    def find_path(
        self, start: Tuple[int, int], goal: Tuple[int, int]
    ) -> List[Tuple[int, int]]:
        """Finds the shortest path from start to goal using A* algorithm."""
        if self.tiles[start[1]][start[0]] in {1, 3, 4} or self.tiles[goal[1]][
            goal[0]
        ] in {1, 3, 4}:
            return []  # No valid path if start/goal is in an obstacle.

        def heuristic(a: Tuple[int, int], b: Tuple[int, int]) -> int:
            """Manhattan distance heuristic function."""
            return abs(a[0] - b[0]) + abs(a[1] - b[1])

        open_set = []
        heapq.heappush(open_set, (0, start))
        came_from = {}
        g_score: Dict[Tuple[int, int], float] = {start: 0}
        f_score: Dict[Tuple[int, int], float] = {start: heuristic(start, goal)}

        directions = [(-1, 0), (1, 0), (0, -1), (0, 1)]  # Left, Right, Up, Down

        while open_set:
            _, current = heapq.heappop(open_set)

            if current == goal:
                path = []
                while current in came_from:
                    path.append(current)
                    current = came_from[current]

                path.append(start)  # Ensure start is included
                path = path[::-1]  # Reverse the path to start -> goal

                return path

            for dx, dy in directions:
                neighbor = (current[0] + dx, current[1] + dy)

                if 0 <= neighbor[0] < self.WIDTH and 0 <= neighbor[1] < self.HEIGHT:
                    tile_type = self.tiles[neighbor[1]][neighbor[0]]

                    if tile_type in {1, 3, 4}:  # Avoid rivers & towers
                        continue
                    move_cost = 1 if tile_type == 0 else 0.5  # Bridges are cheaper

                    tentative_g_score = g_score[current] + move_cost

                    if neighbor not in g_score or tentative_g_score < g_score[neighbor]:
                        came_from[neighbor] = current
                        g_score[neighbor] = tentative_g_score
                        f_score[neighbor] = tentative_g_score + heuristic(
                            neighbor, goal
                        )
                        heapq.heappush(open_set, (f_score[neighbor], neighbor))

        return []  # No path found

    def __str__(self) -> str:
        border = "╔" + "═" * self.WIDTH + "╗"
        tile_symbols = {0: " ", 1: "≈", 2: "═", 3: "▲", 4: "♔"}
        rows = [
            "║" + "".join(tile_symbols[cell] for cell in row) + "║"
            for row in self.tiles
        ]
        bottom_border = "╚" + "═" * self.WIDTH + "╝"
        return "\n".join([border] + rows + [bottom_border])

    def add_unit(self, unit: IDUnit):
        self.units.append(unit)

    def get_target(
        self,
        current_pos: Tuple[int, int],
        target_owner: Owner,
        target_types: List[TargetType],
    ) -> Optional[UnitTarget]:
        """Determines the closest valid target based on owner and target types, prioritizing enemy units."""
        enemy_units: List[IDUnit] = [
            unit
            for unit in self.units
            if unit.inner.owner != target_owner
            and unit.inner.underlying.layer in target_types
            and unit.inner.unit_data.hitpoints > 0
        ]
        if enemy_units:
            closest_enemy = min(
                enemy_units,
                key=lambda unit: abs(current_pos[0] - unit.inner.unit_data.x)
                + abs(current_pos[1] - unit.inner.unit_data.y),
            )
            # path = self.find_path(
            #     current_pos,
            #     (closest_enemy.inner.unit_data.x, closest_enemy.inner.unit_data.y),
            # )
            adjacent_tiles = []
            for dx, dy in [(0, -1), (0, 1), (1, 0), (-1, 0)]:
                nx, ny = (
                    closest_enemy.inner.unit_data.x + dx,
                    closest_enemy.inner.unit_data.y + dy,
                )
                if (
                    0 <= nx < self.WIDTH
                    and 0 <= ny < self.HEIGHT
                    and self.tiles[ny][nx] == 0
                ):
                    adjacent_tiles.append((nx, ny))

            if not adjacent_tiles:
                return None

            best_adjacent_tile: Tuple[int, int] = min(
                adjacent_tiles,
                key=lambda adj: abs(current_pos[0] - adj[0])
                + abs(current_pos[1] - adj[1]),
            )

            return UnitTarget(
                closest_enemy.id,
                UnitTargetType.TROOP,
                self.find_path(current_pos, best_adjacent_tile),
            )

        valid_targets: List[Tuple[UnitTargetType, int, int, TowerId]] = []
        is_princess_tower: bool = False
        is_one_princess_tower: bool = True
        for tower in self.towers:
            if tower.owner == target_owner and tower.current_hp > 0:
                if tower.tower_type == UnitTargetType.PRINCESS_TOWER:
                    if is_princess_tower:
                        is_one_princess_tower = False
                    is_princess_tower = True
                valid_targets.append(
                    (tower.tower_type, tower.center_x, tower.center_y, tower.tower_id)
                )

        if not valid_targets:
            return None

        if is_princess_tower and not is_one_princess_tower:
            for target in valid_targets:
                if target[0] == UnitTargetType.KING_TOWER:
                    valid_targets.remove(target)

        closest_target = min(
            valid_targets,
            key=lambda target: abs(current_pos[0] - target[1])
            + abs(current_pos[1] - target[2]),
        )

        target_x, target_y = closest_target[1], closest_target[2]

        adjacent_tiles = []
        for dx, dy in [(0, -2) if target_owner == Owner.P2 else (0, 2)]:
            nx, ny = target_x + dx, target_y + dy
            if (
                0 <= nx < self.WIDTH
                and 0 <= ny < self.HEIGHT
                and self.tiles[ny][nx] == 0
            ):
                adjacent_tiles.append((nx, ny))

        if not adjacent_tiles:
            return None

        best_adjacent_tile = min(
            adjacent_tiles,
            key=lambda adj: abs(current_pos[0] - adj[0]) + abs(current_pos[1] - adj[1]),
        )

        path = self.find_path(current_pos, best_adjacent_tile)

        return UnitTarget(closest_target[3].value, closest_target[0], path)

    def tower_id_to_target_str(
        self, id: str
    ) -> int:  # returns idx of tower in self.towers
        for i, tower in enumerate(self.towers):
            if tower.tower_id == id:
                return i
        raise ValueError("Invalid Tower ID")

    def tower_id_to_target(self, id: str) -> int:  # returns idx of tower in self.towers
        for i, tower in enumerate(self.towers):
            if tower.tower_id.value == id:
                return i
        raise ValueError("Invalid Tower ID")

    @classmethod
    def is_tower_dead(cls, arena: Self, x: int, y: int) -> bool:
        """Optimized function to check if a tower at (x, y) is dead."""
        tower_id = cls.get_tower_id(arena, (x, y))

        if tower_id is None:
            print("ok")
            return False

        tower_index = cls.tower_id_to_target_str(arena, str(tower_id))
        return arena.towers[tower_index].current_hp <= 0

    @classmethod
    def get_tower_id(cls, arena: Self, pos: Tuple[int, int]) -> Optional[TowerId]:
        """
        Given a position, returns the TowerId if the position is within a tower, otherwise returns None.
        """
        for tower in arena.towers:
            if (
                tower.center_x - 1 <= pos[0] <= tower.center_x + 1
                and tower.center_y - 1 <= pos[1] <= tower.center_y + 1
            ):
                return tower.tower_id
        return None

    def tick(self, units: List[IDUnit]) -> List[IDUnit]:
        """Processes unit actions in the arena."""
        u = units.copy()

        for unit in u:
            if unit.inner.unit_data.current_target and unit.inner.underlying.range:
                if (
                    len(unit.inner.unit_data.current_target.path) - 1
                    < unit.inner.underlying.range
                ):
                    if (
                        unit.inner.unit_data.current_target.unit_type
                        == UnitTargetType.TROOP
                    ):
                        for _unit in u:
                            if (
                                _unit.id == unit.inner.unit_data.current_target.uuid
                                and unit.inner.underlying.damage
                                and unit.inner.underlying.attack_speed
                                and _unit.inner.unit_data.hitpoints > 0
                            ):
                                if is_time_elapsed(
                                    unit.inner.unit_data.last_attack,
                                    unit.inner.underlying.attack_speed,
                                ):
                                    unit.inner.unit_data.last_attack = (
                                        datetime.now().strftime(DATE_FORMAT)
                                    )
                                    _unit.inner.unit_data.hitpoints = (
                                        _unit.inner.unit_data.hitpoints
                                        - unit.inner.underlying.damage
                                    )
                    elif (
                        unit.inner.unit_data.current_target.unit_type
                        == UnitTargetType.BUILDING
                    ):
                        pass
                    else:
                        target_tower = self.tower_id_to_target(
                            unit.inner.unit_data.current_target.uuid
                        )

                        if (
                            self.towers[target_tower].current_hp > 0
                            and unit.inner.underlying.damage
                            and unit.inner.underlying.attack_speed
                        ):
                            if is_time_elapsed(
                                unit.inner.unit_data.last_attack,
                                unit.inner.underlying.attack_speed,
                            ):
                                unit.inner.unit_data.last_attack = (
                                    datetime.now().strftime(DATE_FORMAT)
                                )
                                self.towers[target_tower].current_hp = (
                                    self.towers[target_tower].current_hp
                                    - unit.inner.underlying.damage
                                )

        # self.towers = [tower for tower in self.towers if tower.current_hp > 0]
        # self._set_tower_tiles()

        return units

    @classmethod
    def get_tile_owner(cls, tile: Tuple[int, int]) -> Optional[Owner]:
        if tile[1] <= 13:
            return Owner.P1
        elif tile[1] == 14 or tile[1] == 15:
            return None
        elif tile[1] >= 16:
            return Owner.P2

    @classmethod
    def dist(cls, origin: Tuple[int, int], goal: Tuple[int, int]) -> int:
        path = cls().find_path(origin, goal)
        if not path:
            raise ValueError("Invalid Path")
        return len(path) - 1


def test_pathfinding_basic():
    """Test pathfinding in an open area with no obstacles."""
    arena = Arena()
    start = (5, 5)
    goal = (15, 25)
    path = arena.find_path(start, goal)

    assert path, "Path should be found"
    assert path[0] == start, "Path should start at the given start position"
    assert path[-1] == goal, "Path should end at the goal position"


def test_pathfinding_avoids_obstacles():
    """Ensure pathfinding avoids obstacles like rivers and towers."""
    arena = Arena()
    start = (5, 5)
    goal = (5, arena.HEIGHT - 5)

    path = arena.find_path(start, goal)

    # Ensure path doesn't enter tower or river tiles
    for x, y in path:
        assert arena.tiles[y][x] not in {1, 3, 4}, "Path should not enter obstacles"


def test_pathfinding_uses_bridges():
    """Test that the pathfinder correctly crosses the bridge over the river."""
    arena = Arena()
    start = (5, 5)
    goal = (5, arena.HEIGHT - 5)

    path = arena.find_path(start, goal)

    # Check that at least one step is on the bridge
    bridge_found = any(arena.tiles[y][x] == 2 for x, y in path)
    assert bridge_found, "Path should cross a bridge over the river"


def test_no_path_if_start_in_obstacle():
    """Ensure pathfinding returns an empty path if starting inside an obstacle."""
    arena = Arena()
    start = (arena.WIDTH // 2, 1)  # Inside King Tower
    goal = (5, 5)

    path = arena.find_path(start, goal)
    assert not path, "Path should be empty when starting inside an obstacle"


def test_no_path_if_goal_in_obstacle():
    """Ensure pathfinding returns an empty path if the goal is inside an obstacle."""
    arena = Arena()
    start = (5, 5)
    goal = (arena.WIDTH // 2, 1)  # Inside King Tower

    path = arena.find_path(start, goal)
    assert not path, "Path should be empty when goal is inside an obstacle"


def test_no_valid_path():
    """Test when no path is available (e.g., completely blocked area)."""
    arena = Arena()

    # Manually block a location
    for y in range(5, 10):
        for x in range(5, 10):
            arena.tiles[y][x] = 3  # Block with Crown Towers

    start = (4, 4)
    goal = (6, 6)  # Completely blocked by obstacles

    path = arena.find_path(start, goal)
    assert not path, "Path should be empty when no valid path exists"
