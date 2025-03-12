from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional


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


@dataclass
class Deck:
    cards: List[Card]


ARCHER = Card(
    name="Archer",
    elixir_cost=3,
    card_type=CardType.TROOP,
    rarity=Rarity.COMMON,
    hitpoints=250,
    damage=100,
    attack_speed=1.2,
    range=5.0,
    movement_speed=MovementSpeed.MEDIUM,
    targets=[TargetType.AIR, TargetType.GROUND],
    damage_type=DamageType.SINGLE_TARGET,
)

GIANT = Card(
    name="Giant",
    elixir_cost=5,
    card_type=CardType.TROOP,
    rarity=Rarity.RARE,
    hitpoints=2200,
    damage=250,
    attack_speed=1.5,
    range=0.5,
    movement_speed=MovementSpeed.SLOW,
    targets=[TargetType.BUILDINGS],
    damage_type=DamageType.SINGLE_TARGET,
)

FIREBALL = Card(
    name="Fireball",
    elixir_cost=4,
    card_type=CardType.SPELL,
    rarity=Rarity.RARE,
    damage=575,
    effect_radius=2.5,
    duration=0.5,
    damage_type=DamageType.SPELL,
)

CANNON = Card(
    name="Cannon",
    elixir_cost=3,
    card_type=CardType.BUILDING,
    rarity=Rarity.COMMON,
    hitpoints=900,
    damage=150,
    attack_speed=0.8,
    range=5.5,
    targets=[TargetType.GROUND],
    damage_type=DamageType.SINGLE_TARGET,
    building_lifetime=30.0,
)
