import json
import math
import random
from typing import Dict, Any, List, Optional, Union, override

from bindings import A, D, E, Q, S, W, SDLWrapper
import bindings
from board import Board
from engine import Camera, Camera3D, Component, EngineCode, EngineFrameData, FullGameEngine, GameObject, TextRenderer, Transform, Transform3D
from network import Client
from pipeline import Event, FramePipeline, StateData
import util

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
    def __init__(self, text_renderer: TextRenderer, scale: float = 100):
        super().__init__()
        self.scale = scale
        self.cities: Dict[str, CityData] = {}
        self.board: Optional[Board] = None
        self.text_renderer = text_renderer
        
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

        mousePos = sdl.getMousePosition()
        scaled_radius = int(10 * camera.zoom if camera else 10)

        # Draw connections between cities
        for city_name, city_data in self.cities.items():
            city_pos = city_data.position
            for neighbor in city_data.neighbors:
                neighbor_pos = self.cities[neighbor].position

                x1_world, y1_world = transform.local_to_world(city_pos)
                x2_world, y2_world = transform.local_to_world(neighbor_pos)

                if camera:
                    x1_screen, y1_screen = camera.world_to_screen((x1_world, y1_world, 0))
                    x2_screen, y2_screen = camera.world_to_screen((x2_world, y2_world, 0))
                else:
                    x1_screen, y1_screen = x1_world, y1_world
                    x2_screen, y2_screen = x2_world, y2_world

                dx = x2_screen - x1_screen
                dy = y2_screen - y1_screen
                angle = np.arctan2(dy, dx)

                x1_line = x1_screen + scaled_radius * np.cos(angle)
                y1_line = y1_screen + scaled_radius * np.sin(angle)

                x2_line = x2_screen - scaled_radius * np.cos(angle)
                y2_line = y2_screen - scaled_radius * np.sin(angle)

                sdl.draw_line(int(x1_line), int(y1_line), int(x2_line), int(y2_line), 100, 100, 100)

        # Draw cities
        for city_name, city_data in self.cities.items():
            x, y = transform.local_to_world(city_data.position)
            if camera:
                x, y = camera.world_to_screen((x, y, 0))

            # Draw research center
            if city_data.has_research_center:
                rect_size = int(30 * camera.zoom) if camera else 30
                sdl.draw_rect(int(x) - rect_size // 2, int(y) - rect_size // 2, rect_size, rect_size, 255, 255, 0)

            # Draw city circle
            self.draw_circle(sdl, int(x), int(y), scaled_radius, 200, 200, 200, util.is_point_inside_circle(int(x), int(y), scaled_radius, mousePos[0], mousePos[1]))

            # Draw disease cubes
            num_boxes = 4  # We always have 4 boxes
            angle_increment = 360 / num_boxes  # Angle between boxes


            disease_colors = {
                "blue": 0,
                "red": 1,
                "yellow": 2,
                "black": 3,
            }

            disease_counts = {
                "blue": 0,
                "red": 0,
                "yellow": 0,
                "black": 0,
            }

            for disease_type, count in city_data.diseases.items():
                disease_counts[disease_type] = count

            self.text_renderer.set_font_size(int(5 * camera.zoom) if camera else 10)
            for disease_type, count in disease_counts.items():
                color = self.get_disease_color(disease_type)
                box_index = disease_colors[disease_type]

                # Calculate box position using polar coordinates
                scaled_disease_box_size = int(scaled_radius * 0.5)  # Box size (25% of radius) - Moved inside the loop
                angle_deg = angle_increment * box_index
                angle_rad = np.radians(angle_deg)

                box_x = int(x + (scaled_radius * 0.6) * np.cos(angle_rad))  # Adjust 0.6 for distance from center
                box_y = int(y + (scaled_radius * 0.6) * np.sin(angle_rad))

                # Center the box
                box_x -= scaled_disease_box_size // 2
                box_y -= scaled_disease_box_size // 2

                sdl.draw_rect(box_x, box_y, scaled_disease_box_size, scaled_disease_box_size, *color)

                text_x = box_x + scaled_disease_box_size // 2 - int(self.text_renderer.get_text_width(str(count)) / 2)
                text_y = box_y + scaled_disease_box_size // 2 - int(self.text_renderer.get_font_height(str(count)) / 2)
                self.text_renderer.draw_text(str(count), text_x, text_y, (255, 255, 255))


            # Draw players in this city
            if self.board_state.players:
                num_players_in_city = 0
                for player_name, player_data in self.board_state.players.items():
                    if player_data['location'] == city_name:
                        num_players_in_city += 1

                player_index = 0
                for player_name, player_data in self.board_state.players.items():
                    if player_data['location'] == city_name:
                        color = (255, 255, 0) if player_name == self.board_state.get_current_player() else (255, 255, 255)

                        angle = 2 * np.pi * player_index / num_players_in_city
                        scaled_player_radius = int(6 * camera.zoom) if camera else 6
                        circle_radius = int(25 * camera.zoom) if camera else 25

                        player_x = int(x + circle_radius * np.cos(angle))
                        player_y = int(y + circle_radius * np.sin(angle))

                        self.draw_circle(sdl, player_x, player_y, scaled_player_radius, color[0], color[1], color[2])

                        text_x = player_x - int(self.text_renderer.get_text_width(str(player_index + 1)) / 2)
                        text_y = player_y - int(self.text_renderer.get_font_height(str(player_index)) / 2)
                        self.text_renderer.set_font_size(int(12 * camera.zoom) if camera else 12)
                        self.text_renderer.draw_text(str(player_index + 1), text_x, text_y, (255, 255, 255))

                        player_index += 1
                        
    def draw_circle(self, sdl: SDLWrapper, x: int, y: int, radius: int, r: int, g: int, b: int, fill: bool = False):
        """Draw a circle by approximating it with lines, optionally filled.

        Args:
            sdl: The SDLWrapper object for drawing.
            x: The x-coordinate of the circle's center.
            y: The y-coordinate of the circle's center.
            radius: The radius of the circle.
            r: The red component of the circle's color.
            g: The green component of the circle's color.
            b: The blue component of the circle's color.
            fill: If True, the circle will be filled.  Defaults to False.
        """
        segments = 16  # You can adjust this for smoother/rougher circles

        if fill:
            for i in range(-radius, radius + 1):  # Iterate through x-coordinates
                for j in range(-radius, radius + 1):  # Iterate through y-coordinates
                    if i*i + j*j <= radius*radius:  # Check if point is within circle
                        sdl.draw_point(x + i, y + j, r, g, b)
        else:
            # Draw the outline
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
            "black": (255, 255, 255)
        }
        return colors.get(disease_type, (255, 255, 255))

    def update_renderer(self):
        """Update the renderer with current board state"""
        if self.board:
            self.update_state(self.board)


class PandemicBoard(GameObject):
    def __init__(self, pipeline: FramePipeline[EngineFrameData], client: Client, text_renderer: TextRenderer, player: Client, position: Tuple[int, int] = (400, 300), board: Optional[Board] = None):
        super().__init__(pipeline, "PandemicBoard", position)
        self.add_component(Transform(position))
        self.add_component(PandemicBoardRenderer(text_renderer=text_renderer))
        self.board: Optional[Board] = board 
        self.player = player

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

        self.board = Board(["Bot1", "Bot2", "Bot3", "Player"])

    def tick(self):
        pass

    def start(self):
        self.run(self.tick)

    def render(self, override: bool = True):
        self.sdl.clear_screen(0, 0, 0)
        return super().render(True)
        
    def setup(self):
        self.client = Client("127.0.0.1", 5000, "Player")
        self.text_renderer = TextRenderer(self.sdl)
        self.text_renderer.load_font("/usr/share/fonts/adobe-source-sans/SourceSansPro-Regular.otf", 24)

        self.add_game_object(PandemicBoard, self.client, self.text_renderer, (0, 0), board=self.board)
        
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
        if 0.5 <= new_zoom <= 8.0:  # Clamp zoom to reasonable values
            self.camera.zoom = new_zoom

def clamp(n, min, max): 
	if n < min: 
		return min
	elif n > max: 
		return max
	else: 
		return n 
