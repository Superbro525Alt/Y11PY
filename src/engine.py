from dataclasses import dataclass
from enum import Enum
import threading
import time
from typing import Any, Callable, List, Optional, Tuple, TypeVar
import bindings
from pipeline import Event, EventType, Frame, FrameListener, FramePipeline, PipelineState, PipelineSupplier, StateData
import numpy as np
from util import Pair

class EngineCode(Enum):
    COMPONENT_TICK = 1 

@dataclass 
class EngineFrameData:
    code: EngineCode
    sdl: bindings.SDLWrapper
    camera: Optional["Camera"]

T = TypeVar('T')

class Engine:
    def __init__(self, pipeline: FramePipeline[EngineFrameData], event_pipeline: FramePipeline[Event], state_pipeline: FramePipeline[StateData], window_title: str = "Game Engine", width: int = 800, height: int = 600):

        self.sdl = bindings.SDLWrapper(width, height, window_title)
        self.sdl.initialize()
        self.sdl.create_window()
        self.sdl.create_renderer()
        self.running = False
        self.game_objects: List[GameObject] = []
        self.camera: Optional[Camera] = None

        self.pipeline = pipeline
        self.event_pipeline = event_pipeline
        self.state_pipeline = state_pipeline

        self.state_getters = []
        self.state_setters = []

    def event_loop(self) -> None:
        while True:
            self.event_pipeline.send(Event(EventType.UPDATE_STATE))
            time.sleep(0.1)

    def run(self, secondary: Callable[[], None]):
        """Starts the main game loop."""
        self.running = True
        self.setup()
        threading.Thread(target=self.event_loop, daemon=True).start()

        while self.running:
            # print("tick")
            self.handle_events()
            self.update()
            self.render()
            self.sdl.delay(16)  # ~60 FPS
            secondary()

    def quit(self):
        """Stops the game loop."""
        self.running = False

    def setup(self):
        """Override for initialization logic."""
        pass

    def handle_events(self):
        """Processes SDL events."""
        event = bindings.SDL_Event()
        while self.sdl.poll_event(event):
            if event.type == bindings.SDL_EventType.QUIT:
                self.quit()
            elif event.type == bindings.SDL_EventType.KEYDOWN:
                if event.key.keysym.scancode == bindings.SDL_Scancode.Escape:
                    self.quit()

    def update(self):
        """Updates all game objects."""
        self.pipeline.send(EngineFrameData(EngineCode.COMPONENT_TICK, self.sdl, self.camera))


    def render(self):
        """Renders all game objects."""
        self.sdl.clear_screen(0, 0, 0)  # Clear screen with black
        for game_object in self.game_objects:
            game_object.render(self.sdl, self.camera)
        self.sdl.update_screen()

    def add_game_object(self, game_object: 'GameObject'):
        """Adds a GameObject to the engine."""
        self.game_objects.append(game_object)

    def set_camera(self, camera: 'Camera'):
        """Sets the active camera."""
        self.camera = camera

    def manage(self, data: T) -> Pair[Callable[[], Optional[T]], Callable[[Optional[T]], None]]:
        setter = PipelineSupplier(self.event_pipeline, self.state_pipeline, initial=data)
        getter = PipelineState(setter.get_id(), self.state_pipeline)

        return Pair(lambda: getter.get(), lambda data: setter.update(data))



class Camera:
    def __init__(self, position: Tuple[int, int] = (0, 0), zoom: float = 1.0):
        self.position = list(position)
        self.zoom = zoom

    def world_to_screen(self, point: Tuple[int, int]) -> Tuple[int, int]:
        """Converts world coordinates to screen coordinates."""
        x, y = point
        screen_x = int((x - self.position[0]) * self.zoom)
        screen_y = int((y - self.position[1]) * self.zoom)
        return screen_x, screen_y

    def screen_to_world(self, point: Tuple[int, int]) -> Tuple[int, int]:
        """Converts screen coordinates to world coordinates."""
        screen_x, screen_y = point
        world_x = int(screen_x / self.zoom + self.position[0])
        world_y = int(screen_y / self.zoom + self.position[1])
        return world_x, world_y


class GameObject:
    def __init__(self, pipeline: FramePipeline[EngineFrameData], name: str = "GameObject", position: Tuple[int, int] = (0, 0)):
        self.name = name
        self.position = list(position)
        self.components: List[Component] = []
        self.pipeline = pipeline
        
        pipeline.attach(FrameListener(pipeline, lambda frame: self.update(frame.data)))

    def add_component(self, component: 'Component'):
        """Adds a component to the GameObject."""
        if not isinstance(component, Component):
            raise TypeError("Must add a Component subclass")
        component.game_object = self
        self.components.append(component)
        component.awake()

    def remove_component(self, component: 'Component'):
        """Removes a component from the GameObject."""
        if component in self.components:
            component.on_disable()
            self.components.remove(component)
            component.game_object = None

    def find_component(self, component_type: type) -> Optional[Any]:
        """Finds the first component of the specified type."""
        for comp in self.components:
            if isinstance(comp, component_type):
                return comp
        return None

    def update(self, frame: EngineFrameData):
        """Updates all components."""
        if frame.code == EngineCode.COMPONENT_TICK:
            for comp in self.components:
                comp.update()
                comp.render(frame.sdl, frame.camera)

    def render(self, sdl: bindings.SDLWrapper, camera: Optional[Camera] = None):
        """Renders all components."""
        for comp in self.components:
            comp.render(sdl, camera)


class Component:
    def __init__(self):
        self.game_object: Optional[GameObject] = None

    def awake(self):
        """Called when the component is added to a GameObject."""
        pass

    def on_enable(self):
        """Called when the component is enabled."""
        pass

    def on_disable(self):
        """Called when the component is disabled."""
        pass

    def update(self):
        """Called every frame for game logic."""
        pass

    def render(self, sdl: bindings.SDLWrapper, camera: Optional[Camera] = None):
        """Called every frame for rendering."""
        pass

class Transform(Component):
    def __init__(self, position: Tuple[float, float] = (0.0, 0.0), rotation: float = 0.0, scale: Tuple[float, float] = (1.0, 1.0)):
        super().__init__()
        self.position = np.array(position, dtype=float)
        self.rotation = rotation  # In degrees
        self.scale = np.array(scale, dtype=float)
        self._matrix = None  # Cache the transformation matrix

    def set_position(self, position: Tuple[float, float]):
        self.position = np.array(position, dtype=float)
        self._matrix = None  # Invalidate the matrix cache

    def set_rotation(self, rotation: float):
        self.rotation = rotation
        self._matrix = None

    def set_scale(self, scale: Tuple[float, float]):
        self.scale = np.array(scale, dtype=float)
        self._matrix = None

    def get_matrix(self) -> np.ndarray:
        if self._matrix is None:
            # Create the transformation matrix only when needed and cache it
            translation_matrix = np.array([[1, 0, self.position[0]],
                                          [0, 1, self.position[1]],
                                          [0, 0, 1]], dtype=float)

            rotation_matrix = np.array([[np.cos(np.radians(self.rotation)), -np.sin(np.radians(self.rotation)), 0],
                                        [np.sin(np.radians(self.rotation)), np.cos(np.radians(self.rotation)), 0],
                                        [0, 0, 1]], dtype=float)

            scale_matrix = np.array([[self.scale[0], 0, 0],
                                     [0, self.scale[1], 0],
                                     [0, 0, 1]], dtype=float)

            # Order of transformations: Scale -> Rotate -> Translate
            self._matrix = translation_matrix @ rotation_matrix @ scale_matrix
        return self._matrix

    def world_to_local(self, world_point: Tuple[float, float]) -> np.ndarray:
        """Converts world coordinates to local coordinates."""
        world_point_3d = np.array([world_point[0], world_point[1], 1], dtype=float)
        inverse_matrix = np.linalg.inv(self.get_matrix())
        local_point_3d = inverse_matrix @ world_point_3d
        return local_point_3d[:2]  # Return the 2D local point

    def local_to_world(self, local_point: Tuple[float, float]) -> np.ndarray:
         """Converts local coordinates to world coordinates."""
         local_point_3d = np.array([local_point[0], local_point[1], 1], dtype=float)
         world_point_3d = self.get_matrix() @ local_point_3d
         return world_point_3d[:2]  # Return the 2D world point

    def get_global_position(self) -> np.ndarray:
        """Gets the GameObject's position in world space."""
        return self.position

    def get_global_rotation(self) -> float:
        """Gets the GameObject's rotation in world space."""
        return self.rotation

    def get_global_scale(self) -> np.ndarray:
        """Gets the GameObject's scale in world space."""
        return self.scale


class SpriteRenderer(Component):
    def __init__(self):
        super().__init__()

    def awake(self):
        if self.game_object is None:
            raise RuntimeError("SpriteRenderer must be attached to a GameObject.")

    def render(self, sdl: bindings.SDLWrapper, camera: Optional[Camera] = None):
        if self.game_object is None:
            return

        transform = self.game_object.find_component(Transform)  

        if transform is None:
            raise RuntimeError("SpriteRenderer requires a Transform component.")

        matrix = transform.get_matrix()

        if camera:
            screen_x, screen_y = camera.world_to_screen(transform.get_global_position())
        else:
            screen_x, screen_y = transform.get_global_position()

        sdl.draw_rect(int(screen_x), int(screen_y), 100, 100, 255, 0, 0)
