import json
import random
from typing import Dict, Any, List

def pretty_print_board(board_state):
    """Prints the game board in a readable format."""
    print("\n" + "=" * 50)
    print(f" 🌍 PANDEMIC GAME BOARD - TURN {board_state['turn']} 🌍")
    print(f"Current Turn: {board_state['current_turn']} | Actions Left: {board_state['actions_remaining']}")
    print("=" * 50)

    # Print Players
    print("\n👥 Players:")
    for player, data in board_state["players"].items():
        print(f"  - {player}: {data['location']}")

    # Print Cities
    print("\n🏙️ Cities:")
    for city, data in board_state["cities"].items():
        research_center = "🏥" if data["research_center"] else "   "
        diseases = ", ".join([f"{color}: {count}" for color, count in data.get("disease", {}).items()])
        diseases = diseases if diseases else "None"
        print(f"  {research_center} {city:<15} | Diseases: {diseases}")

    print("\n" + "=" * 50)

class Board:
    CITIES = {
        "San Francisco": {"neighbors": ["Los Angeles", "Chicago", "Tokyo", "Manila"], "research_center": False, "disease": {}},
        "Los Angeles": {"neighbors": ["San Francisco", "Mexico City", "Sydney", "Chicago"], "research_center": False, "disease": {}},
        "Chicago": {"neighbors": ["San Francisco", "Los Angeles", "Montreal", "Atlanta", "Mexico City"], "research_center": False, "disease": {}},
        "Montreal": {"neighbors": ["Chicago", "New York", "Washington"], "research_center": False, "disease": {}},
        "New York": {"neighbors": ["Montreal", "Washington", "Madrid", "London"], "research_center": False, "disease": {}},
        "Washington": {"neighbors": ["New York", "Montreal", "Miami", "Atlanta"], "research_center": False, "disease": {}},
        "Atlanta": {"neighbors": ["Chicago", "Washington", "Miami"], "research_center": True, "disease": {}},
        "Miami": {"neighbors": ["Washington", "Atlanta", "Bogotá", "Mexico City"], "research_center": False, "disease": {}},
        "Mexico City": {"neighbors": ["Los Angeles", "Chicago", "Miami", "Bogotá", "Lima"], "research_center": False, "disease": {}},
        "Bogotá": {"neighbors": ["Mexico City", "Miami", "Lima", "São Paulo", "Buenos Aires"], "research_center": False, "disease": {}},
        "Lima": {"neighbors": ["Mexico City", "Bogotá", "Santiago"], "research_center": False, "disease": {}},
        "Santiago": {"neighbors": ["Lima"], "research_center": False, "disease": {}},
        "Buenos Aires": {"neighbors": ["Bogotá", "São Paulo"], "research_center": False, "disease": {}},
        "São Paulo": {"neighbors": ["Bogotá", "Buenos Aires", "Madrid", "Lagos"], "research_center": False, "disease": {}},
        "Lagos": {"neighbors": ["São Paulo", "Kinshasa", "Khartoum"], "research_center": False, "disease": {}},
        "Khartoum": {"neighbors": ["Lagos", "Kinshasa", "Johannesburg", "Cairo"], "research_center": False, "disease": {}},
        "Kinshasa": {"neighbors": ["Lagos", "Khartoum", "Johannesburg"], "research_center": False, "disease": {}},
        "Johannesburg": {"neighbors": ["Kinshasa", "Khartoum"], "research_center": False, "disease": {}},
        "Madrid": {"neighbors": ["New York", "São Paulo", "Paris", "London", "Algiers"], "research_center": False, "disease": {}},
        "London": {"neighbors": ["New York", "Madrid", "Paris", "Essen"], "research_center": False, "disease": {}},
        "Paris": {"neighbors": ["London", "Madrid", "Essen", "Algiers", "Milan"], "research_center": False, "disease": {}},
        "Essen": {"neighbors": ["London", "Paris", "Milan", "St. Petersburg"], "research_center": False, "disease": {}},
        "Milan": {"neighbors": ["Essen", "Paris", "Istanbul"], "research_center": False, "disease": {}},
        "Algiers": {"neighbors": ["Madrid", "Paris", "Cairo", "Istanbul"], "research_center": False, "disease": {}},
        "Cairo": {"neighbors": ["Algiers", "Istanbul", "Baghdad", "Khartoum"], "research_center": False, "disease": {}},
        "Istanbul": {"neighbors": ["Milan", "Algiers", "Cairo", "Baghdad", "Moscow", "St. Petersburg"], "research_center": False, "disease": {}},
        "Moscow": {"neighbors": ["St. Petersburg", "Istanbul", "Tehran"], "research_center": False, "disease": {}},
        "St. Petersburg": {"neighbors": ["Essen", "Istanbul", "Moscow"], "research_center": False, "disease": {}},
        "Baghdad": {"neighbors": ["Istanbul", "Cairo", "Riyadh", "Tehran", "Karachi"], "research_center": False, "disease": {}},
        "Manila": {"neighbors": ["Taipei", "San Francisco", "Ho Chi Minh City", "Sydney", "Hong Kong"], "research_center": False, "disease": {}},
        "Sydney": {"neighbors": ["Jakarta", "Los Angeles", "Manila"], "research_center": False, "disease": {}},
        "Tehran": {"neighbors": ["Baghdad", "Moscow", "Delhi", "Karachi"], "research_center": False, "disease": {}},
        "Tokyo": {"neighbors": ["Seoul", "Shanghai", "San Francisco", "Osaka"], "research_center": False, "disease": {}},
        "Delhi": {"neighbors": ["Tehran", "Karachi", "Mumbai", "Chennai", "Kolkata"], "research_center": False, "disease": {}},
        "Ho Chi Minh City": {"neighbors": ["Jakarta", "Bangkok", "Manila", "Hong Kong"], "research_center": False, "disease": {}},
        "Hong Kong": {"neighbors": ["Shanghai", "Taipei", "Manila", "Ho Chi Minh City", "Bangkok", "Kolkata"], "research_center": False, "disease": {}},
        "Jakarta": {"neighbors": ["Chennai", "Bangkok", "Ho Chi Minh City", "Sydney"], "research_center": False, "disease": {}},
        "Karachi": {"neighbors": ["Baghdad", "Tehran", "Delhi", "Mumbai", "Riyadh"], "research_center": False, "disease": {}},
        "Osaka": {"neighbors": ["Taipei", "Tokyo"], "research_center": False, "disease": {}},
        "Riyadh": {"neighbors": ["Baghdad", "Karachi", "Cairo"], "research_center": False, "disease": {}},
        "Seoul": {"neighbors": ["Beijing", "Shanghai", "Tokyo"], "research_center": False, "disease": {}},
        "Shanghai": {"neighbors": ["Beijing", "Seoul", "Tokyo", "Taipei", "Hong Kong"], "research_center": False, "disease": {}},
        "Taipei": {"neighbors": ["Shanghai", "Hong Kong", "Osaka", "Manila"], "research_center": False, "disease": {}},
        "Bangkok": {"neighbors": ["Kolkata", "Chennai", "Jakarta", "Ho Chi Minh City", "Hong Kong"], "research_center": False, "disease": {}},
        "Beijing": {"neighbors": ["Shanghai", "Seoul"], "research_center": False, "disease": {}},
        "Chennai": {"neighbors": ["Mumbai", "Delhi", "Kolkata", "Bangkok", "Jakarta"], "research_center": False, "disease": {}},
        "Kolkata": {"neighbors": ["Delhi", "Chennai", "Bangkok", "Hong Kong"], "research_center": False, "disease": {}},
        "Mumbai": {"neighbors": ["Karachi", "Delhi", "Chennai"], "research_center": False, "disease": {}},
    }

    def __init__(self, player_names: List[str]):
        """Initialize the board with cities, players, diseases, and turn tracking."""
        self.cities = {city: data.copy() for city, data in self.CITIES.items()}
        self.players = {name: {"location": "Atlanta", "role": None} for name in player_names}
        self.turn_order = list(self.players.keys())  # Order of turns
        self.current_turn_index = 0  # Index of whose turn it is
        self.actions_per_turn = 4
        self.actions_remaining = self.actions_per_turn
        self.diseases = {"blue": 0, "red": 0, "yellow": 0, "black": 0}
        self.outbreaks = 0
        self.turn = 0
        self.infection_deck = list(self.CITIES.keys())
        random.shuffle(self.infection_deck)
        self.player_deck = []  # Placeholder for player card deck

    def get_current_player(self):
        """Returns the name of the current player."""
        return self.turn_order[self.current_turn_index]

    def move(self, player: str, destination: str):
        """Moves a player to a neighboring city."""
        if self.get_current_player() != player:
            print(f"{player} cannot move, it's not their turn.")
            return False
        
        if destination in self.CITIES[self.players[player]["location"]]["neighbors"]:
            self.players[player]["location"] = destination
            self.actions_remaining -= 1
            print(f"{player} moved to {destination}.")
            return True
        else:
            print("Invalid move!")
            return False

    def treat_disease(self, player: str):
        """Treats one cube of disease in the player's current city."""
        if self.get_current_player() != player:
            print(f"{player} cannot treat disease, it's not their turn.")
            return False

        city = self.players[player]["location"]
        if self.cities[city]["disease"]:
            disease_type = next(iter(self.cities[city]["disease"]))
            self.cities[city]["disease"][disease_type] -= 1
            if self.cities[city]["disease"][disease_type] == 0:
                del self.cities[city]["disease"][disease_type]
            self.actions_remaining -= 1
            print(f"{player} treated {disease_type} disease in {city}.")
            return True
        else:
            print(f"No disease to treat in {city}.")
            return False

    def cure_disease(self, player: str, disease_type: str):
        """Cures a disease if the player has enough cards."""
        if self.get_current_player() != player:
            print(f"{player} cannot cure disease, it's not their turn.")
            return False

        # Assume players need 5 matching cards (simplified for now)
        if disease_type in self.diseases and self.diseases[disease_type] > 0:
            self.diseases[disease_type] = 0  # Cure disease
            self.actions_remaining -= 1
            print(f"{player} cured {disease_type} disease!")
            return True
        else:
            print(f"{disease_type} disease is not active.")
            return False

    def build_research_station(self, player: str):
        """Builds a research station in the player's current city."""
        if self.get_current_player() != player:
            print(f"{player} cannot build, it's not their turn.")
            return False

        city = self.players[player]["location"]
        self.cities[city]["research_center"] = True
        self.actions_remaining -= 1
        print(f"{player} built a research station in {city}.")
        return True

    def pass_turn(self, player: str):
        """Ends the player's turn early."""
        if self.get_current_player() != player:
            print(f"{player} cannot pass, it's not their turn.")
            return False

        self.actions_remaining = 0
        self.end_turn()

    def end_turn(self):
        """Ends the turn, advances turn order, and resets actions."""
        self.current_turn_index = (self.current_turn_index + 1) % len(self.turn_order)
        self.actions_remaining = self.actions_per_turn
        self.turn += 1
        self.infect_city()
        print(f"Turn {self.turn} ended. Next player: {self.get_current_player()}.")

    def infect_city(self):
        """Infects a random city from the infection deck."""
        if not self.infection_deck:
            return

        city = self.infection_deck.pop(0)
        disease_type = random.choice(["blue", "red", "yellow", "black"])
        self.cities[city]["disease"][disease_type] = self.cities[city]["disease"].get(disease_type, 0) + 1
        print(f"{city} infected with {disease_type}.")

    def tick_turn(self):
        """Processes end-of-turn events."""
        self.infect_city()
        print(f"End of turn {self.turn}. {self.get_current_player()}'s turn begins.")

    def update_from_server(self, game_state: Dict[str, Any]):
        """Updates the board state with data from the server."""
        self.__dict__.update(game_state)

    def broadcast_state(self) -> Dict[str, Any]:
        """Returns the current game state for sending to clients."""
        return {
            "players": self.players,
            "turn_order": self.turn_order,
            "current_turn": self.get_current_player(),
            "actions_remaining": self.actions_remaining,
            "cities": self.cities,
            "diseases": self.diseases,
            "outbreaks": self.outbreaks,
            "turn": self.turn,
            "infection_deck": self.infection_deck
        }

    def __repr__(self):
        return json.dumps(self.broadcast_state(), indent=2)

