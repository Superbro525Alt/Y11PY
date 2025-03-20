from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional, Self, Tuple
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

    @classmethod
    def to_num(cls, speed: Self) -> float:
        if speed == cls.SLOW.value:
            return 4
        elif speed == cls.MEDIUM.value:
            return 3
        elif speed == cls.FAST.value:
            return 2
        elif speed == cls.VERY_FAST.value:
            return 1
        else:
            return 9999


class TargetType(Enum):
    GROUND = "Ground"
    AIR = "Air"
    BOTH = "Both"
    BUILDINGS = "Buildings"
    NONE = "None"  # Spell


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
    layer: TargetType
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


def from_namespace(namespace):
    """Converts a namespace object to a Card dataclass instance."""

    card_type = CardType(namespace.card_type)
    rarity = Rarity(namespace.rarity)
    layer = TargetType(namespace.layer)
    movement_speed = MovementSpeed(namespace.movement_speed)

    targets = [TargetType(target) for target in namespace.targets]

    damage_type = DamageType(namespace.damage_type) if namespace.damage_type else None

    card = Card(
        name=namespace.name,
        elixir_cost=namespace.elixir_cost,
        card_type=card_type,
        rarity=rarity,
        layer=layer,
        hitpoints=namespace.hitpoints,
        damage=namespace.damage,
        attack_speed=namespace.attack_speed,
        range=namespace.range,
        deploy_time=namespace.deploy_time,
        special_ability=namespace.special_ability,
        targets=targets,
        movement_speed=movement_speed,
        duration=namespace.duration,
        damage_type=damage_type,
        spawn_units=namespace.spawn_units,
        building_lifetime=namespace.building_lifetime,
        effect_radius=namespace.effect_radius,
        projectile_speed=namespace.projectile_speed,
        spawn_damage=namespace.spawn_damage,
    )

    return card


GOBLIN_SHAMAN = Card(
    name="Goblin Shaman",
    elixir_cost=3,
    card_type=CardType.TROOP,
    rarity=Rarity.RARE,
    layer=TargetType.GROUND,
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
    layer=TargetType.GROUND,
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
    layer=TargetType.GROUND,
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
    layer=TargetType.GROUND,
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
    layer=TargetType.AIR,
    hitpoints=400,
    damage=150,
    attack_speed=1.8,
    range=7.0,
    movement_speed=MovementSpeed.FAST,
    targets=[TargetType.AIR, TargetType.GROUND],
    damage_type=DamageType.SINGLE_TARGET,
    special_ability="Ignores ground units, can only be targeted by air units and spells.",
)

EARTHQUAKE = Card(
    name="Earthquake",
    elixir_cost=3,
    card_type=CardType.SPELL,
    rarity=Rarity.EPIC,
    layer=TargetType.NONE,
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
    layer=TargetType.GROUND,
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
    layer=TargetType.GROUND,
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
    layer=TargetType.GROUND,
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
    layer=TargetType.NONE,
    duration=5.0,
    damage_type=DamageType.SPELL,
    special_ability="Creates two weaker copies of the last deployed troop.",
)

VOLCANO_TRAP = Card(
    name="Volcano Trap",
    elixir_cost=4,
    card_type=CardType.BUILDING,
    rarity=Rarity.EPIC,
    layer=TargetType.GROUND,
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
    layer=TargetType.GROUND,
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
    layer=TargetType.GROUND,
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
    layer=TargetType.GROUND,
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
    layer=TargetType.GROUND,
    hitpoints=1800,
    damage=100,
    attack_speed=1.3,
    range=1.0,
    movement_speed=MovementSpeed.MEDIUM,
    targets=[TargetType.BUILDINGS, TargetType.GROUND],
    damage_type=DamageType.SINGLE_TARGET,
    special_ability="Upon death, splits into two Elixir Blobs which give the opponent 1 elixir each when killed.",
)
