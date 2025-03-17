from datetime import datetime, timedelta
from typing import Optional
from arena import Arena
from card import CardType, MovementSpeed
from unit import IDUnit, Owner
from util import DATE_FORMAT
from copy import copy

def card_tick(_card: IDUnit, arena: Arena) -> Optional[IDUnit]:
    card = copy(_card)

    card.inner.unit_data.current_target = arena.get_target((card.inner.unit_data.x, card.inner.unit_data.y), card.inner.owner, card.inner.underlying.targets)

    if card.inner.unit_data.current_target:
        if not card.inner.unit_data.current_target:
            return  # No target, so do nothing

        path = card.inner.unit_data.current_target.path
        if not path or len(path) < 2:
            return  # No path available, prevent errors

        last_move_time = datetime.strptime(card.inner.unit_data.last_move, DATE_FORMAT)
    
        next_move_time = last_move_time + timedelta(seconds=MovementSpeed.to_num(card.inner.underlying.movement_speed))
    
        if datetime.now().timestamp() - next_move_time.timestamp() > 0 and card.inner.underlying.card_type == CardType.TROOP.value:
            print("move")
            card.inner.unit_data.x, card.inner.unit_data.y = path[1]

            card.inner.unit_data.last_move = datetime.now().strftime(DATE_FORMAT)
        
        return card
