from dataclasses import dataclass, field
from typing import List, Optional

from card import Card
from chest import Chest
from clan import Clan
from deck import Deck


@dataclass
class LoginRequest:
    password_hash: str
    username: str


@dataclass
class LoginResponse:
    uuid: str
    username: str


@dataclass
class ServerUserData:
    chests: List[Chest]
    clan: Optional[Clan]
    trophies: int
    decks: List[Deck]
    current_deck: int
    current_battle: Optional[str]
    gold: int = 1000
    cards: List[Card] = field(default_factory=lambda: [])

@dataclass
class User:
    username: str
    uuid: str
    pass_hash: str
    data: ServerUserData


class UserMap:
    def __init__(self, initial_users: List[User]) -> None:
        self.users = {user.username: user for user in initial_users}
        self.users_by_uuid = {user.uuid: user for user in initial_users}

    def find(self, name: str, password_hash: str) -> Optional[User]:
        user = self.users.get(name)
        if user and user.pass_hash == password_hash:
            return user
        return None

    def find_uuid(self, uuid: str) -> Optional[User]:
        return self.users_by_uuid.get(uuid)

    def update_trophies(self, uuid: str, diff: int) -> None:
        u = self.find_uuid(uuid)
        if u:
            u.data.trophies += diff
            self.users.update({uuid: u})

    def update_battle(self, user_id: str, battle_id: Optional[str]):
        user = self.find_uuid(user_id)
        if user:
            user.data.current_battle = battle_id
            self.users.update({user_id: user})


@dataclass
class DataRequest:
    uuid: str
