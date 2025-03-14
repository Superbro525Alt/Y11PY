from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Tuple
import heapq

class CardType(Enum):
    TROOP = "Troop"
    BUILDING = "Building"
    SPELL = "Spell"


class Rarity(Enum):
    COMMON = "Common"
    RARE = "Rare"
    EPIC = "Epic"
    LEGENDARY = "Legendary"
    CHAMPION = "Champion"


class MovementSpeed(Enum):
    SLOW = "Slow"
    MEDIUM = "Medium"
    FAST = "Fast"
    VERY_FAST = "Very Fast"
    NONE = "None"  # For buildings and spells


class TargetType(Enum):
    GROUND = "Ground"
    AIR = "Air"
    BOTH = "Both"
    BUILDINGS = "Buildings"


class DamageType(Enum):
    SINGLE_TARGET = "Single Target"
    SPLASH = "Splash"
    AREA_DAMAGE = "Area Damage"
    SPELL = "Spell"


@dataclass
class Card:
    name: str
    elixir_cost: int
    card_type: CardType
    rarity: Rarity
    hitpoints: Optional[int] = None  # Not applicable to spells
    damage: Optional[int] = None  # Not applicable to buildings
    attack_speed: Optional[float] = None  # Not applicable to spells
    range: Optional[float] = None  # Not applicable to melee troops
    deploy_time: float = 1.0
    special_ability: str = ""
    targets: List[TargetType] = field(default_factory=lambda: [])
    movement_speed: MovementSpeed = MovementSpeed.NONE
    duration: Optional[float] = None  # Only for spells and some abilities
    damage_type: Optional[DamageType] = None
    spawn_units: Optional[List[str]] = None  # For cards like Graveyard, Goblin Barrel
    building_lifetime: Optional[float] = (
        None  # Only for buildings with limited lifespan
    )
    effect_radius: Optional[float] = None  # Only for splash/area damage or spells
    projectile_speed: Optional[float] = None  # Only for ranged units and spells
    spawn_damage: Optional[int] = (
        None  # Damage dealt when deploying (e.g., Electro Wizard)
    )


def card_tick(card: Card) -> None:
    pass


@dataclass
class Deck:
    cards: List[Card]


GOBLIN_SHAMAN = Card(
    name="Goblin Shaman",
    elixir_cost=3,
    card_type=CardType.TROOP,
    rarity=Rarity.RARE,
    hitpoints=350,
    damage=80,
    attack_speed=1.8,
    range=4.5,
    movement_speed=MovementSpeed.MEDIUM,
    targets=[TargetType.GROUND, TargetType.AIR],
    damage_type=DamageType.SINGLE_TARGET,
    special_ability="Heals nearby allies for 50 HP every 3 seconds.",
)

ROCK_GOLEM = Card(
    name="Rock Golem",
    elixir_cost=6,
    card_type=CardType.TROOP,
    rarity=Rarity.EPIC,
    hitpoints=3000,
    damage=300,
    attack_speed=2.0,
    range=1.0,
    movement_speed=MovementSpeed.SLOW,
    targets=[TargetType.BUILDINGS, TargetType.GROUND],
    damage_type=DamageType.SINGLE_TARGET,
    special_ability="Upon death, splits into two smaller Rock Golems with half HP and damage.",
)

ICE_SPIKES = Card(
    name="Ice Spikes",
    elixir_cost=3,
    card_type=CardType.SPELL,
    rarity=Rarity.COMMON,
    damage=150,
    effect_radius=3.0,
    duration=2.0,
    damage_type=DamageType.SPELL,
    special_ability="Slows enemy movement and attack speed by 30% for the duration.",
)

POISON_TOWER = Card(
    name="Poison Tower",
    elixir_cost=4,
    card_type=CardType.BUILDING,
    rarity=Rarity.RARE,
    hitpoints=1100,
    damage=30,
    attack_speed=1.0,
    range=6.0,
    targets=[TargetType.GROUND, TargetType.AIR],
    damage_type=DamageType.AREA_DAMAGE,
    building_lifetime=40.0,
    special_ability="Deals poison damage over time, reducing enemy healing by 50%.",
)

SKY_ARCHER = Card(
    name="Sky Archer",
    elixir_cost=4,
    card_type=CardType.TROOP,
    rarity=Rarity.EPIC,
    hitpoints=400,
    damage=150,
    attack_speed=1.5,
    range=7.0,
    movement_speed=MovementSpeed.FAST,
    targets=[TargetType.AIR],
    damage_type=DamageType.SINGLE_TARGET,
    special_ability="Ignores ground units, can only be targeted by air units and spells.",
)

EARTHQUAKE = Card(
    name="Earthquake",
    elixir_cost=3,
    card_type=CardType.SPELL,
    rarity=Rarity.EPIC,
    damage=200,
    effect_radius=4.0,
    duration=3.0,
    damage_type=DamageType.SPELL,
    special_ability="Deals extra damage to buildings, stuns ground units for 0.5 seconds upon impact.",
)

LUMBERJACK_GOBLIN = Card(
    name="Lumberjack Goblin",
    elixir_cost=4,
    card_type=CardType.TROOP,
    rarity=Rarity.RARE,
    hitpoints=600,
    damage=200,
    attack_speed=0.9,
    range=1.0,
    movement_speed=MovementSpeed.VERY_FAST,
    targets=[TargetType.GROUND],
    damage_type=DamageType.SINGLE_TARGET,
    special_ability="Drops a Rage spell upon death.",
)

ARCANE_CANNON = Card(
    name="Arcane Cannon",
    elixir_cost=5,
    card_type=CardType.BUILDING,
    rarity=Rarity.EPIC,
    hitpoints=1200,
    damage=250,
    attack_speed=2.0,
    range=6.5,
    targets=[TargetType.BOTH],
    damage_type=DamageType.SPLASH,
    building_lifetime=35.0,
    special_ability="Attacks both ground and air with splash damage.",
)

SPECTRAL_KNIGHT = Card(
    name="Spectral Knight",
    elixir_cost=4,
    card_type=CardType.TROOP,
    rarity=Rarity.LEGENDARY,
    hitpoints=800,
    damage=220,
    attack_speed=1.1,
    range=1.2,
    movement_speed=MovementSpeed.FAST,
    targets=[TargetType.GROUND],
    damage_type=DamageType.SINGLE_TARGET,
    special_ability="Phases through units, immune to ground traps.",
)

MIRROR_IMAGE = Card(
    name="Mirror Image",
    elixir_cost=3,
    card_type=CardType.SPELL,
    rarity=Rarity.LEGENDARY,
    duration=5.0,
    damage_type=DamageType.SPELL,
    special_ability="Creates two weaker copies of the last deployed troop.",
)

VOLCANO_TRAP = Card(
    name="Volcano Trap",
    elixir_cost=4,
    card_type=CardType.BUILDING,
    rarity=Rarity.EPIC,
    building_lifetime=20.0,
    special_ability="Activates when a ground unit approaches, erupting and dealing massive area damage.",
    effect_radius=3.5,
    damage=800,
    damage_type=DamageType.AREA_DAMAGE,
)

TIME_WIZARD = Card(
    name="Time Wizard",
    elixir_cost=5,
    card_type=CardType.TROOP,
    rarity=Rarity.LEGENDARY,
    hitpoints=650,
    damage=180,
    attack_speed=1.7,
    range=5.0,
    movement_speed=MovementSpeed.MEDIUM,
    targets=[TargetType.BOTH],
    damage_type=DamageType.SINGLE_TARGET,
    special_ability="Has a 30% chance to slow down enemy attack speed and movement by 50% for 2 seconds with each attack.",
)

GOBLIN_DRILL = Card(
    name="Goblin Drill",
    elixir_cost=4,
    card_type=CardType.BUILDING,
    rarity=Rarity.EPIC,
    building_lifetime=30.0,
    special_ability="Periodically spawns Goblins from underground near enemy towers.",
    spawn_units=["Goblin"],
    attack_speed=10,  # placeholder, does not attack
    targets=[],  # does not attack
)

SHADOW_ASSASSIN = Card(
    name="Shadow Assassin",
    elixir_cost=3,
    card_type=CardType.TROOP,
    rarity=Rarity.LEGENDARY,
    hitpoints=500,
    damage=280,
    attack_speed=1.0,
    range=1.0,
    movement_speed=MovementSpeed.VERY_FAST,
    targets=[TargetType.GROUND],
    damage_type=DamageType.SINGLE_TARGET,
    special_ability="Becomes invisible for 3 seconds after deploying or when out of combat for 5 seconds. Deals double damage when attacking from invisibility.",
)

ELIXIR_GOLEM = Card(
    name="Elixir Golem",
    elixir_cost=3,
    card_type=CardType.TROOP,
    rarity=Rarity.EPIC,
    hitpoints=1800,
    damage=100,
    attack_speed=1.3,
    range=1.0,
    movement_speed=MovementSpeed.MEDIUM,
    targets=[TargetType.BUILDINGS, TargetType.GROUND],
    damage_type=DamageType.SINGLE_TARGET,
    special_ability="Upon death, splits into two Elixir Blobs which give the opponent 1 elixir each when killed.",
)

class TileType(Enum):
    EMPTY = 0        # Walkable tile
    RIVER = 1        # Water (unwalkable)
    BRIDGE = 2       # Bridge over river
    CROWN_TOWER = 3  # Crown Tower (3x3 structure)
    KING_TOWER = 4   # King Tower (3x3 structure)

class Arena:
    WIDTH: int = 19
    HEIGHT: int = 30

    def __init__(self) -> None:
        self.tiles = [
            [TileType.EMPTY.value for _ in range(self.WIDTH)] for _ in range(self.HEIGHT)
        ]

        for x in range(self.WIDTH):
            self.tiles[self.HEIGHT // 2 - 1][x] = TileType.RIVER.value
            self.tiles[self.HEIGHT // 2][x] = TileType.RIVER.value

        for dy in range(2):
            self.tiles[self.HEIGHT // 2 - 1 + dy][4] = TileType.BRIDGE.value
            self.tiles[self.HEIGHT // 2 - 1 + dy][15] = TileType.BRIDGE.value

        king_x = self.WIDTH // 2
        for dx in range(-1, 2):
            for dy in range(-1, 2):
                self.tiles[2 + dy][king_x + dx] = TileType.KING_TOWER.value  # Move forward
                self.tiles[self.HEIGHT - 3 + dy][king_x + dx] = TileType.KING_TOWER.value

        crown_positions = [(3, 3), (3, self.WIDTH - 4), (self.HEIGHT - 4, 3), (self.HEIGHT - 4, self.WIDTH - 4)]
        for y, x in crown_positions:
            for dx in range(-1, 2):
                for dy in range(-1, 2):
                    self.tiles[y + dy][x + dx] = TileType.CROWN_TOWER.value  # Move forward


    def find_path(self, start: Tuple[int, int], goal: Tuple[int, int]) -> List[Tuple[int, int]]:
        """Finds the shortest path from start to goal using A* algorithm."""
        if self.tiles[start[1]][start[0]] in {1, 3, 4} or self.tiles[goal[1]][goal[0]] in {1, 3, 4}:
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
                        f_score[neighbor] = tentative_g_score + heuristic(neighbor, goal)
                        heapq.heappush(open_set, (f_score[neighbor], neighbor))

        return []  # No path found

    def __str__(self) -> str:
        border = "╔" + "═" * self.WIDTH + "╗"
        tile_symbols = {0: " ", 1: "≈", 2: "═", 3: "▲", 4: "♔"}
        rows = ["║" + "".join(tile_symbols[cell] for cell in row) + "║" for row in self.tiles]
        bottom_border = "╚" + "═" * self.WIDTH + "╝"
        return "\n".join([border] + rows + [bottom_border])

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

