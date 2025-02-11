import json
import random
from typing import Dict, Any, List, Optional, Union, override

from bindings import A, D, E, Q, S, W, SDLWrapper
from engine import Camera, Camera3D, Component, EngineCode, EngineFrameData, FullGameEngine, GameObject, Transform, Transform3D
from pipeline import Event, FramePipeline, StateData

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
                "San Francisco": {"neighbors": ["Los Angeles", "Chicago", "Tokyo", "Manila"], "research_center": False, "disease": {}, "x": -2, "y": 2},
        "Los Angeles": {"neighbors": ["San Francisco", "Mexico City", "Sydney", "Chicago"], "research_center": False, "disease": {}, "x": -3, "y": 1},
        "Chicago": {"neighbors": ["San Francisco", "Los Angeles", "Montreal", "Atlanta", "Mexico City"], "research_center": False, "disease": {}, "x": -1, "y": 2},
        "Montreal": {"neighbors": ["Chicago", "New York", "Washington"], "research_center": False, "disease": {}, "x": 0, "y": 3},
        "New York": {"neighbors": ["Montreal", "Washington", "Madrid", "London"], "research_center": False, "disease": {}, "x": 1, "y": 3},
        "Washington": {"neighbors": ["New York", "Montreal", "Miami", "Atlanta"], "research_center": False, "disease": {}, "x": 1, "y": 2},
        "Atlanta": {"neighbors": ["Chicago", "Washington", "Miami"], "research_center": True, "disease": {}, "x": 0, "y": 1},
        "Miami": {"neighbors": ["Washington", "Atlanta", "Bogotá", "Mexico City"], "research_center": False, "disease": {}, "x": 2, "y": 1},
        "Mexico City": {"neighbors": ["Los Angeles", "Chicago", "Miami", "Bogotá", "Lima"], "research_center": False, "disease": {}, "x": -2, "y": -1},
        "Bogotá": {"neighbors": ["Mexico City", "Miami", "Lima", "São Paulo", "Buenos Aires"], "research_center": False, "disease": {}, "x": 1, "y": -2},
        "Lima": {"neighbors": ["Mexico City", "Bogotá", "Santiago"], "research_center": False, "disease": {}, "x": 0, "y": -3},
        "Santiago": {"neighbors": ["Lima"], "research_center": False, "disease": {}, "x": -1, "y": -4},
        "Buenos Aires": {"neighbors": ["Bogotá", "São Paulo"], "research_center": False, "disease": {}, "x": 2, "y": -3},
        "São Paulo": {"neighbors": ["Bogotá", "Buenos Aires", "Madrid", "Lagos"], "research_center": False, "disease": {}, "x": 2, "y": -2},
        "Lagos": {"neighbors": ["São Paulo", "Kinshasa", "Khartoum"], "research_center": False, "disease": {}, "x": 3, "y": -1},
        "Khartoum": {"neighbors": ["Lagos", "Kinshasa", "Johannesburg", "Cairo"], "research_center": False, "disease": {}, "x": 4, "y": 0},
        "Kinshasa": {"neighbors": ["Lagos", "Khartoum", "Johannesburg"], "research_center": False, "disease": {}, "x": 3, "y": -2},
        "Johannesburg": {"neighbors": ["Kinshasa", "Khartoum"], "research_center": False, "disease": {}, "x": 4, "y": -2},
        "Madrid": {"neighbors": ["New York", "São Paulo", "Paris", "London", "Algiers"], "research_center": False, "disease": {}, "x": 2, "y": 2},
        "London": {"neighbors": ["New York", "Madrid", "Paris", "Essen"], "research_center": False, "disease": {}, "x": 1, "y": 4},
        "Paris": {"neighbors": ["London", "Madrid", "Essen", "Algiers", "Milan"], "research_center": False, "disease": {}, "x": 2, "y": 4},
        "Essen": {"neighbors": ["London", "Paris", "Milan", "St. Petersburg"], "research_center": False, "disease": {}, "x": 2, "y": 5},
        "Milan": {"neighbors": ["Essen", "Paris", "Istanbul"], "research_center": False, "disease": {}, "x": 3, "y": 4},
        "Algiers": {"neighbors": ["Madrid", "Paris", "Cairo", "Istanbul"], "research_center": False, "disease": {}, "x": 3, "y": 2},
        "Cairo": {"neighbors": ["Algiers", "Istanbul", "Baghdad", "Khartoum"], "research_center": False, "disease": {}, "x": 4, "y": 1},
        "Istanbul": {"neighbors": ["Milan", "Algiers", "Cairo", "Baghdad", "Moscow", "St. Petersburg"], "research_center": False, "disease": {}, "x": 4, "y": 3},
        "Moscow": {"neighbors": ["St. Petersburg", "Istanbul", "Tehran"], "research_center": False, "disease": {}, "x": 5, "y": 4},
        "St. Petersburg": {"neighbors": ["Essen", "Istanbul", "Moscow"], "research_center": False, "disease": {}, "x": 4, "y": 5},
        "Baghdad": {"neighbors": ["Istanbul", "Cairo", "Riyadh", "Tehran", "Karachi"], "research_center": False, "disease": {}, "x": 5, "y": 2},
        "Manila": {"neighbors": ["Taipei", "San Francisco", "Ho Chi Minh City", "Sydney", "Hong Kong"], "research_center": False, "disease": {}, "x": -4, "y": -1},
        "Sydney": {"neighbors": ["Jakarta", "Los Angeles", "Manila"], "research_center": False, "disease": {}, "x": -5, "y": -3},
        "Tehran": {"neighbors": ["Baghdad", "Moscow", "Delhi", "Karachi"], "research_center": False, "disease": {}, "x": 6, "y": 3},
        "Tokyo": {"neighbors": ["Seoul", "Shanghai", "San Francisco", "Osaka"], "research_center": False, "disease": {}, "x": -3, "y": 4},
        "Delhi": {"neighbors": ["Tehran", "Karachi", "Mumbai", "Chennai", "Kolkata"], "research_center": False, "disease": {}, "x": 7, "y": 2},
        "Ho Chi Minh City": {"neighbors": ["Jakarta", "Bangkok", "Manila", "Hong Kong"], "research_center": False, "disease": {}, "x": -4, "y": -2},
        "Hong Kong": {"neighbors": ["Shanghai", "Taipei", "Manila", "Ho Chi Minh City", "Bangkok", "Kolkata"], "research_center": False, "disease": {}, "x": -3, "y": -2},
        "Jakarta": {"neighbors": ["Chennai", "Bangkok", "Ho Chi Minh City", "Sydney"], "research_center": False, "disease": {}, "x": -5, "y": -2},
    "Karachi": {"neighbors": ["Baghdad", "Tehran", "Delhi", "Mumbai", "Riyadh"], "research_center": False, "disease": {}, "x": 6, "y": 1},
        "Osaka": {"neighbors": ["Taipei", "Tokyo"], "research_center": False, "disease": {}, "x": -2, "y": 3},
        "Riyadh": {"neighbors": ["Baghdad", "Karachi", "Cairo"], "research_center": False, "disease": {}, "x": 6, "y": 0},
        "Seoul": {"neighbors": ["Beijing", "Shanghai", "Tokyo"], "research_center": False, "disease": {}, "x": -2, "y": 5},
        "Shanghai": {"neighbors": ["Beijing", "Seoul", "Tokyo", "Taipei", "Hong Kong"], "research_center": False, "disease": {}, "x": -3, "y": 3},
        "Taipei": {"neighbors": ["Shanghai", "Hong Kong", "Osaka", "Manila"], "research_center": False, "disease": {}, "x": -3, "y": 2},
        "Bangkok": {"neighbors": ["Kolkata", "Chennai", "Jakarta", "Ho Chi Minh City", "Hong Kong"], "research_center": False, "disease": {}, "x": -4, "y": 0},
        "Beijing": {"neighbors": ["Shanghai", "Seoul"], "research_center": False, "disease": {}, "x": -3, "y": 5},
        "Chennai": {"neighbors": ["Mumbai", "Delhi", "Kolkata", "Bangkok", "Jakarta"], "research_center": False, "disease": {}, "x": 8, "y": 1},
        "Kolkata": {"neighbors": ["Delhi", "Chennai", "Bangkok", "Hong Kong"], "research_center": False, "disease": {}, "x": 7, "y": 0},
        "Mumbai": {"neighbors": ["Karachi", "Delhi", "Chennai"], "research_center": False, "disease": {}, "x": 7, "y": 2},
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
            self.infection_deck = list(self.CITIES.keys())
            random.shuffle(self.infection_deck)

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

from dataclasses import dataclass
from typing import Dict, List, Tuple
import numpy as np

@dataclass
class CityData:
    name: str
    position: Tuple[float, float]
    neighbors: List[str]
    has_research_center: bool
    diseases: Dict[str, int]

@dataclass
class BoardState:
    cities: Dict[str, Dict]
    players: Dict[str, Dict]
    current_turn: str
    actions_remaining: int

class PandemicBoardRenderer(Component):
    def __init__(self, scale: float = 100):
        super().__init__()
        self.scale = scale
        self.cities: Dict[str, CityData] = {}
        self.board: Optional[Board] = None
        
    def update_state(self, board_state: Board):
        """Update the renderer with new board state"""
        self.board_state = board_state
        # Convert city data into our format with normalized coordinates
        self.cities = {}
        for name, data in board_state.cities.items():
            pos_data = Board.CITIES[name]
            self.cities[name] = CityData(
                name=name,
                position=(pos_data['x'] * self.scale, pos_data['y'] * self.scale),
                neighbors=pos_data['neighbors'],
                has_research_center=data['research_center'],
                diseases=data.get('disease', {})
            )
        
    def render(self, sdl: SDLWrapper, camera: Optional[Union[Camera, Camera3D]] = None):
        if not self.game_object or not self.board_state:
            return
            
        transform = self.game_object.find_component(Transform)
        if not transform:
            return
            
        # Draw connections between cities
        for city_name, city_data in self.cities.items():
            city_pos = city_data.position
            for neighbor in city_data.neighbors:
                neighbor_pos = self.cities[neighbor].position
                x1, y1 = transform.local_to_world(city_pos)
                x2, y2 = transform.local_to_world(neighbor_pos)
                if camera:
                    x1, y1 = camera.world_to_screen((x1, y1, 0))
                    x2, y2 = camera.world_to_screen((x2, y2, 0))
                sdl.draw_line(int(x1), int(y1), int(x2), int(y2), 100, 100, 100)
        
        # Draw cities
        for city_name, city_data in self.cities.items():
            x, y = transform.local_to_world(city_data.position)
            if camera:
                x, y = camera.world_to_screen((x, y, 0))
            
            # Draw research center
            if city_data.has_research_center:
                sdl.draw_rect(int(x) - 15, int(y) - 15, 30, 30, 255, 255, 0)
            
            # Draw city circle
            self.draw_circle(sdl, int(x), int(y), 10, 200, 200, 200)
            
            # Draw disease cubes
            if city_data.diseases:
                offset = 0
                for disease_type, count in city_data.diseases.items():
                    color = self.get_disease_color(disease_type)
                    for i in range(count):
                        sdl.draw_rect(int(x) + offset, int(y) + 15, 5, 5, *color)
                        offset += 7
            
            # Draw players in this city
            if self.board_state.players:
                player_offset = 0
                for player_name, player_data in self.board_state.players.items():
                    if player_data['location'] == city_name:
                        # Highlight current player
                        color = (255, 255, 0) if player_name == self.board_state.get_current_player() else (255, 255, 255)
                        sdl.draw_circle(int(x) - 5 + player_offset, int(y) - 20, 5, *color)
                        player_offset += 12
                        
    def draw_circle(self, sdl: SDLWrapper, x: int, y: int, radius: int, r: int, g: int, b: int):
        """Draw a circle by approximating it with lines."""
        segments = 16
        for i in range(segments):
            angle1 = 2 * np.pi * i / segments
            angle2 = 2 * np.pi * (i + 1) / segments
            x1 = int(x + radius * np.cos(angle1))
            y1 = int(y + radius * np.sin(angle1))
            x2 = int(x + radius * np.cos(angle2))
            y2 = int(y + radius * np.sin(angle2))
            sdl.draw_line(x1, y1, x2, y2, r, g, b)
            
    def get_disease_color(self, disease_type: str) -> Tuple[int, int, int]:
        """Return RGB color for each disease type."""
        colors = {
            "blue": (0, 0, 255),
            "red": (255, 0, 0),
            "yellow": (255, 255, 0),
            "black": (0, 0, 0)
        }
        return colors.get(disease_type, (255, 255, 255))

    def update_renderer(self):
        """Update the renderer with current board state"""
        if self.board:
            self.update_state(self.board)


class PandemicBoard(GameObject):
    def __init__(self, pipeline: FramePipeline[EngineFrameData], position: Tuple[int, int] = (400, 300), board: Optional[Board] = None):
        super().__init__(pipeline, "PandemicBoard", position)
        self.add_component(Transform(position))
        self.add_component(PandemicBoardRenderer())
        self.board: Optional[Board] = board 

    def set_board(self, board: Board):
        """Set the game board and update the renderer"""
        self.board = board


    def update(self, frame: EngineFrameData):
        c = self.find_component(PandemicBoardRenderer)
        if c is not None:
            c.update_state(self.board)
        if frame.code == EngineCode.COMPONENT_TICK:
            for comp in self.components:
                comp.update()
                comp.render(frame.sdl, frame.camera)

class PandemicGame(FullGameEngine):
    def __init__(self):
        engine_pipe = FramePipeline[EngineFrameData]("engine_pipe")
        event_pipe = FramePipeline[Event]("event_pipe")
        state_pipe = FramePipeline[StateData]("state_pipe")

        super().__init__(engine_pipe, event_pipe, state_pipe, 
                        window_title="Pandemic Board Test",
                        width=1200, height=800)
        
        # Initialize camera with some zoom
        self.camera = Camera((0, 0), zoom=0.75, screen_width=1200, screen_height=800)
        self.camera_speed = 10
        self.zoom_speed = 0.05

        self.board = Board(["Bot1", "Bot2", "Bot3", "Bot4"])

    def tick(self):
        pass

    def start(self):
        self.run(self.tick)

    def render(self, override: bool = True):
        self.sdl.clear_screen(0, 100, 0)
        return super().render(True)
        
    def setup(self):
        self.add_game_object(PandemicBoard, (0, 0), board=self.board)
        
        self.input_manager.register_key_down(W, lambda: self.move_camera(0, -self.camera_speed))
        self.input_manager.register_key_down(S, lambda: self.move_camera(0, self.camera_speed))
        self.input_manager.register_key_down(A, lambda: self.move_camera(-self.camera_speed, 0))
        self.input_manager.register_key_down(D, lambda: self.move_camera(self.camera_speed, 0))
        self.input_manager.register_key_down(Q, lambda: self.adjust_zoom(-self.zoom_speed))
        self.input_manager.register_key_down(E, lambda: self.adjust_zoom(self.zoom_speed))
        
    def move_camera(self, dx: float, dy: float):
        """Move the camera by the given delta."""
        self.camera.position[0] += dx
        self.camera.position[1] += dy
        
    def adjust_zoom(self, delta: float):
        """Adjust the camera zoom level."""
        new_zoom = self.camera.zoom + delta
        if 0.1 <= new_zoom <= 2.0:  # Clamp zoom to reasonable values
            self.camera.zoom = new_zoom
