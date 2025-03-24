from datetime import datetime, timedelta
from typing import Optional
from arena import Arena
from card import CardType, MovementSpeed
from unit import IDUnit, Owner
from util import DATE_FORMAT
from copy import copy


def card_tick(_card: IDUnit, arena: Arena) -> Optional[IDUnit]:
    card = copy(_card)
    card.inner.unit_data.current_target = arena.get_target(
        (card.inner.unit_data.x, card.inner.unit_data.y),
        card.inner.owner,
        card.inner.underlying.targets,
    )
    if (
        card.inner.unit_data.current_target
        and (path := card.inner.unit_data.current_target.path)
        and len(path) > 1
        and card.inner.underlying.card_type == CardType.TROOP.value
        and datetime.now().timestamp()
        - (
            datetime.strptime(card.inner.unit_data.last_move, DATE_FORMAT)
            + timedelta(
                seconds=MovementSpeed.to_num(card.inner.underlying.movement_speed)
            )
        ).timestamp()
        > 0
    ):
        if (
            card.inner.underlying.range
            and not len(card.inner.unit_data.current_target.path) - 1
            < card.inner.underlying.range
        ):
            card.inner.unit_data.x, card.inner.unit_data.y = path[1]
            card.inner.unit_data.last_move = datetime.now().strftime(DATE_FORMAT)

    return card if card.inner.unit_data.current_target else None
