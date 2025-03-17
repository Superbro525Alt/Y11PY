from datetime import datetime, timedelta
from arena import Arena
from card import CardType, MovementSpeed
from unit import IDUnit, Owner

def card_tick(card: IDUnit, arena: Arena) -> None:
    card.inner.unit_data.current_target = arena.get_target((card.inner.unit_data.x, card.inner.unit_data.y), card.inner.owner, card.inner.underlying.targets)

    if card.inner.unit_data.current_target:
        path = card.inner.unit_data.current_target.path

        if datetime.now() > card.inner.unit_data.last_move + timedelta(seconds=MovementSpeed.to_num(card.inner.underlying.movement_speed)) and card.inner.underlying.card_type == CardType.TROOP:
            card.inner.unit_data.x = path[0][0]
            card.inner.unit_data.y = path[0][1]
