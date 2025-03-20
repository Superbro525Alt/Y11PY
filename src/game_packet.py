from dataclasses import dataclass
import enum

from deck import Deck


@dataclass
class MatchRequest:
    trophies: int
    uuid: str
    deck: Deck


@dataclass
class MatchFound:
    match_uuid: str
    other_uuid: str
    p: str


class PacketType(enum.Enum):
    """Defines different types of network packets."""

    STATUS = 0
    """
    Server status updates.
    Purpose: Provides clients with information about the server's health and operational state.
    Payload: Server load (CPU, memory), number of connected players, server uptime, maintenance messages,
             and any other relevant server-side metrics.
    """

    HANDSHAKE = 1
    """
    Initial connection negotiation.
    Purpose: Establishes a secure and compatible connection between the client and server.
    Payload: Client's protocol version, client's unique identifier (if available),
             and any other necessary initial connection parameters.
    """

    CONNECTION = 2
    """
    Established connection confirmation.
    Purpose: Signals that the server has successfully established a connection with the client.
    Payload: Server-assigned client ID, server's current timestamp, and any other connection confirmation data.
    """

    DISCONNECT = 3
    """
    Client or server disconnection.
    Purpose: Signals that a client or the server is disconnecting from the network.
    Payload: Reason for disconnection (e.g., "connection lost," "client closed," "server shutdown"),
             client ID (if disconnecting client).
    """

    RECONNECT = 4
    """
    Client attempts to rejoin a match.
    Purpose: Allows clients to reconnect to ongoing matches after a temporary disconnection.
    Payload: Client's unique ID, match ID, reconnection timestamp, and any necessary reconnection tokens.
    """

    SERVER_CLIENT_SYNC = 5
    """
    Server to client game state synchronization.
    Purpose: Provides clients with up-to-date information about the game state.
    Payload: Current game time, unit positions, unit health, tower status, elixir amounts,
             and any other dynamic game state data.
    """

    CLIENT_SERVER_SYNC = 6
    """
    Client to server action synchronization.
    Purpose: Transmits player actions from the client to the server for validation and processing.
    Payload: Player actions (e.g., unit deployment, movement commands, attack commands),
             timestamps, and any other action-related data.
    """

    USER_TO_SERVER_SYNC = 7
    """
    User account data to server.
    Purpose: Updates or saves user account data on the server.
    Payload: User profile data (e.g., username, avatar), deck configurations, in-game settings,
             and any other persistent user data.
    """

    SERVER_TO_USER_SYNC = 8
    """
    Server account data to user.
    Purpose: Transfers user account data from the server to the client.
    Payload: User profile data, deck configurations, currency amounts, trophy counts,
             and any other relevant user data.
    """

    LOGIN = 9
    """
    Client login request.
    Purpose: Authenticates a user's credentials with the server.
    Payload: Username, password, and any other authentication data.
    """

    LOGIN_SUCCESS = 10
    """
    Server confirms successful login.
    Purpose: Notifies the client that login was successful.
    Payload: User's unique ID, authentication token, and any other session data.
    """

    LOGIN_FAIL = 11
    """
    Server signals login failure.
    Purpose: Notifies the client that login failed.
    Payload: Error message describing the reason for failure.
    """

    MATCH_REQUEST = 12
    """
    Client requests a match.
    Purpose: Initiates the matchmaking process.
    Payload: Player's trophy count or matchmaking rating, preferred game mode.
    """

    MATCH_FOUND = 13
    """
    Server informs clients a match is ready.
    Purpose: Notifies clients that a match has been found.
    Payload: Match ID, opponent's player ID, and any other match information.
    """

    MATCH_START = 14
    """
    Server signals the beginning of a match.
    Purpose: Notifies clients that the match is starting.
    Payload: Match seed, starting elixir amounts, and any other initial match data.
    """

    MATCH_END = 15
    """
    Server signals the end of a match.
    Purpose: Notifies clients that the match has ended.
    Payload: Win/loss/draw result, trophy changes, and any other end-of-match data.
    """

    DEPLOY_UNIT = 16
    """
    Client deploys a unit.
    Purpose: Transmits unit deployment actions to the server.
    Payload: Unit ID, deployment coordinates, and any other deployment parameters.
    """

    DEPLOY_SPELL = 17
    """
    Client deploys a spell.
    Purpose: Transmits spell deployment actions to the server.
    Payload: Spell ID, target coordinates, and any other spell parameters.
    """

    DEPLOY_BUILDING = 18
    """
    Client deploys a building.
    Purpose: Transmits building deployment actions to the server.
    Payload: Building ID, deployment coordinates, and any other building parameters.
    """

    UNIT_MOVE = 19
    """
    Client or server updates unit movement.
    Purpose: Transmits unit movement updates.
    Payload: Unit ID, target coordinates, movement speed, and any other movement parameters.
    """

    UNIT_ATTACK = 20
    """
    Client or server updates unit attack.
    Purpose: Transmits unit attack actions.
    Payload: Unit ID, target unit/tower ID, attack damage, and any other attack parameters.
    """

    UNIT_ABILITY = 21
    """
    Client or server updates unit ability use.
    Purpose: Transmits unit ability activation actions.
    Payload: Unit ID, ability ID, target unit/coordinates, and any other ability parameters.
    """

    DAMAGE_UNIT = 22
    """
    Server updates unit damage.
    Purpose: Transmits damage dealt to units.
    Payload: Target unit ID, damage amount, and source of damage.
    """

    DAMAGE_TOWER = 23
    """
    Server updates tower damage.
    Purpose: Transmits damage dealt to towers.
    Payload: Target tower ID, damage amount, and source of damage.
    """

    UNIT_DEATH = 24
    """
    Server updates unit death.
    Purpose: Notifies clients of unit deaths.
    Payload: Unit ID.
    """

    TOWER_DESTRUCTION = 25
    """
    Server updates tower destruction.
    Purpose: Notifies clients of tower destructions.
    Payload: Tower ID.
    """

    ELIXIR_UPDATE = 26
    """
    Server or client updates elixir amount.
    Purpose: Transmits elixir amount updates.
    Payload: Player ID, new elixir amount.
    """

    CHAT_MESSAGE = 27
    """
    Client sends a chat message.
    Purpose: Transmits chat messages between players.
    Payload: Message text, sender ID, and any other chat parameters.
    """

    EMOTE = 28
    """
    Client sends an emote.
    Purpose: Transmits emote actions.
    Payload: Emote ID, sender ID, and any other emote parameters.
    """

    PING = 29
    """
    Client ping request.
    Purpose: Measures network latency.
    Payload: Timestamp.
    """

    PONG = 30
    """
    Server pong response.
    Purpose: Responds to ping requests.
    Payload: Timestamp.
    """

    MENU_REQUEST = 31
    """
    Request initial menu data.
    Purpose: Requests the initial data for the main menu screen.
    Payload: Client Version number.
    """

    MENU_DATA = 32
    """
    Send initial menu data.
    Purpose: Sends the initial data for the main menu screen.
    Payload: Player profile, currency, trophies, friends, news, etc.
    """

    CHEST_REQUEST = 33
    """
    Request chest data.
    Purpose: Requests the player's chest inventory.
    Payload: None.
    """

    CHEST_DATA = 34
    """
    Send chest data.
    Purpose: Sends the player's chest inventory.
    Payload: List of chests (type, timer, rewards).
    """

    CHEST_OPEN = 35
    """
    Request to open a chest.
    Purpose: Requests to open a specific chest.
    Payload: Chest ID.
    """

    CHEST_OPEN_RESULT = 36
    """
    Result of opening a chest.
    Purpose: Sends the result of opening a chest.
    Payload: Rewards (cards, gold, etc.), success/failure status.
    """

    DECK_REQUEST = 37
    """
    Request deck data.
    Purpose: Requests the player's deck configurations.
    Payload: None.
    """

    DECK_DATA = 38
    """
    Send deck data.
    Purpose: Sends the player's deck configurations.
    Payload: List of decks, each containing a list of card IDs and their positions within the deck.
    """

    DECK_UPDATE = 39
    """
    Update deck configuration.
    Purpose: Sends updated deck configurations from the client to the server.
    Payload: Updated list of decks, each containing a list of card IDs and their positions.
    """

    SHOP_REQUEST = 40
    """
    Request shop data.
    Purpose: Requests the current shop inventory.
    Payload: None.
    """

    SHOP_DATA = 41
    """
    Send shop data.
    Purpose: Sends the current shop inventory.
    Payload: List of items for sale (card IDs, gold amounts, chest types), prices, and availability.
    """

    SHOP_PURCHASE = 42
    """
    Request to purchase an item.
    Purpose: Requests to purchase an item from the shop.
    Payload: Item ID.
    """

    SHOP_PURCHASE_RESULT = 43
    """
    Result of shop purchase.
    Purpose: Sends the result of a shop purchase.
    Payload: Success/failure status, updated player currency, and purchased item details.
    """

    CARD_REQUEST = 44
    """
    Request card data.
    Purpose: Requests the player's card inventory.
    Payload: None.
    """

    CARD_DATA = 45
    """
    Send card data.
    Purpose: Sends the player's card inventory.
    Payload: List of cards (card IDs, levels, quantities).
    """

    CARD_UPGRADE = 46
    """
    Request to upgrade a card.
    Purpose: Requests to upgrade a specific card.
    Payload: Card ID.
    """

    CARD_UPGRADE_RESULT = 47
    """
    Result of card upgrade.
    Purpose: Sends the result of a card upgrade.
    Payload: Success/failure status, updated card level, and updated player currency.
    """

    CLAN_REQUEST = 48
    """
    Request clan data.
    Purpose: Requests clan information.
    Payload: Clan ID (optional, if requesting specific clan data).
    """

    CLAN_DATA = 49
    """
    Send clan data.
    Purpose: Sends clan information.
    Payload: Clan name, description, member list, donations, clan trophies, and other relevant clan data.
    """

    CLAN_CREATE = 50
    """
    Request to create a clan.
    Purpose: Requests to create a new clan.
    Payload: Clan name, description, settings (e.g., required trophies).
    """

    CLAN_CREATE_RESULT = 51
    """
    Result of clan creation.
    Purpose: Sends the result of clan creation.
    Payload: Success/failure status, clan ID (if successful).
    """

    CLAN_JOIN = 52
    """
    Request to join a clan.
    Purpose: Requests to join a specific clan.
    Payload: Clan ID.
    """

    CLAN_JOIN_RESULT = 53
    """
    Result of joining a clan.
    Purpose: Sends the result of joining a clan.
    Payload: Success/failure status.
    """

    CLAN_LEAVE = 54
    """
    Request to leave a clan.
    Purpose: Requests to leave the current clan.
    Payload: Clan ID.
    """

    CLAN_LEAVE_RESULT = 55
    """
    Result of leaving a clan.
    Purpose: Sends the result of leaving a clan.
    Payload: Success/failure status.
    """

    CLAN_CHAT = 56
    """
    Clan chat message.
    Purpose: Sends a chat message to the clan chat.
    Payload: Message text, sender ID.
    """

    CLAN_DONATION = 57
    """
    Request to donate cards.
    Purpose: Requests to donate cards to a clan member.
    Payload: Card ID, amount, target player ID.
    """

    CLAN_DONATION_RESULT = 58
    """
    Result of card donation.
    Purpose: Sends the result of a card donation.
    Payload: Success/failure status, updated player inventories.
    """
