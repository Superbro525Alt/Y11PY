from dataclasses import dataclass
from enum import Enum
from logging import Logger
import threading
import time
from typing import (
    Any,
    Callable,
    Dict,
    Generic,
    List,
    Optional,
    Self,
    Tuple,
    Type,
    TypeGuard,
    TypeVar,
    Union,
    overload,
)
import bindings
from pipeline import (
    Event,
    EventType,
    Frame,
    FrameListener,
    FramePipeline,
    ManagedState,
    PipelineState,
    PipelineSupplier,
    StateData,
)
import numpy as np
from util import Pair, logger
import uuid

from bindings import SDLWrapper, SDL_EventType, SDL_Scancode, SDL_Event

from typing import List, Tuple


def intersects(p: Tuple[float, float], v: List[Tuple[float, float]]) -> bool:
    return (
        sum(
            (y1 > p[1]) != (y2 > p[1])
            and p[0] < (x2 - x1) * (p[1] - y1) / (y2 - y1) + x1
            for (x1, y1), (x2, y2) in zip(v, v[1:] + v[:1])
        )
        % 2
        == 1
    )


class EngineCode(Enum):
    COMPONENT_TICK = 1


@dataclass
class EngineFrameData:
    code: EngineCode
    sdl: bindings.SDLWrapper
    camera: Optional[Union["Camera", "Camera3D"]]


T = TypeVar("T")


class InternalEngine:
    def __init__(
        self,
        pipeline: FramePipeline[EngineFrameData],
        event_pipeline: FramePipeline[Event],
        state_pipeline: FramePipeline[StateData],
        window_title: str = "Game Engine",
        width: int = 800,
        height: int = 600,
    ):
        self.sdl = bindings.SDLWrapper(width, height, window_title)
        self.sdl.initialize()
        self.sdl.create_window()
        self.sdl.create_renderer()
        self.running = False
        self.game_objects: List[GameObject] = []
        self.camera: Optional[Union["Camera", "Camera3D"]] = None
        self.pipeline = pipeline
        self.event_pipeline = event_pipeline
        self.state_pipeline = state_pipeline
        self.states: Dict[
            str, Tuple[Callable[[], Optional[Any]], Callable[[Optional[Any]], None]]
        ] = {}

    def event_loop(self) -> None:
        while True:
            self.event_pipeline.send(Event(EventType.UPDATE_STATE))
            time.sleep(0.1)

    def run_with_delay(self, delay: float, call: Callable[[], None]) -> None:
        while True:
            call()
            time.sleep(delay)

    def run(self, secondary: Callable[[], None]):
        self.running = True
        self.setup()
        threading.Thread(target=self.event_loop, daemon=True).start()
        threading.Thread(
            target=lambda: self.run_with_delay(0, secondary), daemon=True
        ).start()
        while self.running:
            self.handle_events()
            self.update()
            self.render()
            self.sdl.delay(16)  # ~60 FPS

    def quit(self):
        self.running = False

    def setup(self):
        # Override for initialization logic.
        pass

    def handle_events(self):
        event = SDL_Event()
        while self.sdl.poll_event(event):
            if event.type == SDL_EventType.QUIT:
                self.quit()
            elif event.type == SDL_EventType.KEYDOWN:
                if event.key.keysym.scancode == SDL_Scancode.Escape:
                    self.quit()

    def update(self):
        self.pipeline.send(
            EngineFrameData(EngineCode.COMPONENT_TICK, self.sdl, self.camera)
        )

    def render(self, override: bool = False):
        if not override:
            self.sdl.clear_screen(0, 0, 0)
        for game_object in self.game_objects:
            game_object.render(self.sdl, self.camera)
        self.sdl.update_screen()

    def add_game_object(self, game_object: Callable[..., Any], *args, **kwargs):
        instance = game_object(self.pipeline, *args, **kwargs)
        if not isinstance(instance, GameObject):
            raise TypeError("Added object must be a subclass of GameObject")
        self.game_objects.append(instance)

    def set_camera(self, camera: Union["Camera", "Camera3D"]):
        self.camera = camera

    def manage(
        self, data: Union[Any, ManagedState]
    ) -> Tuple[Callable[[], Optional[Any]], Callable[[Optional[Any]], None]]:
        u = str(uuid.uuid4())
        if isinstance(data, ManagedState):
            self.states[u] = (lambda: data.get(), lambda new: data.update(new))
            return self.states[u]
        else:
            ms = ManagedState(data, self.event_pipeline, self.state_pipeline)
            self.states[u] = (lambda: ms.get(), lambda new: ms.update(new))
            return self.states[u]

    def with_callback(self, callback: Callable[[Self], None]) -> None:
        callback(self)


# ---- 2D and 3D Camera Classes ----
class Camera:
    def __init__(
        self,
        position: Tuple[int, int] = (0, 0),
        zoom: float = 1.0,
        screen_width: int = 1200,
        screen_height: int = 800,
    ):
        self.position = list(position)
        self.zoom = zoom
        self.screen_width = screen_width
        self.screen_height = screen_height

    def world_to_screen(self, point: Tuple[float, float, float]) -> Tuple[int, int]:
        x, y, _ = point
        screen_x = int((x - self.position[0]) * self.zoom + self.screen_width / 2)
        screen_y = int((y - self.position[1]) * self.zoom + self.screen_height / 2)
        return (screen_x, screen_y)

    def screen_to_world(self, point: Tuple[int, int]) -> Tuple[int, int]:
        screen_x, screen_y = point
        return (
            int(screen_x / self.zoom + self.position[0]),
            int(screen_y / self.zoom + self.position[1]),
        )


class Camera3D:
    def __init__(
        self,
        position: Tuple[float, float, float],
        target: Tuple[float, float, float],
        up: Tuple[float, float, float] = (0, 1, 0),
        fov: float = 60,
        near: float = 0.1,
        far: float = 1000,
        width: float = 800,
        height: float = 600,
    ):
        self.position = np.array(position, dtype=float)
        self.target = np.array(target, dtype=float)
        self.up = np.array(up, dtype=float)
        self.fov = fov
        self.near = near
        self.far = far
        self.screen_width = width
        self.screen_height = height
        self.zoom = 1

    def get_view_matrix(self) -> np.ndarray:
        return look_at(self.position, self.target, self.up)

    def get_projection_matrix(self, aspect: float) -> np.ndarray:
        return perspective(self.fov, aspect, self.near, self.far)

    def world_to_screen(self, point: Tuple[float, float, float]) -> Tuple[int, int]:
        """
        Convert 3D world coordinates to 2D screen coordinates.

        Args:
            point: 3D point in world space (x, y, z)
            screen_width: Width of the screen in pixels
            screen_height: Height of the screen in pixels

        Returns:
            Tuple of (screen_x, screen_y) coordinates
        """
        # Convert point to homogeneous coordinates
        world_pos = np.array([*point, 1.0])

        # Get view and projection matrices
        view_matrix = self.get_view_matrix()
        proj_matrix = self.get_projection_matrix(self.screen_width / self.screen_height)

        # Transform point to clip space
        clip_space = proj_matrix @ view_matrix @ world_pos

        # Perform perspective division
        if clip_space[3] == 0:
            return (0, 0)  # Or handle this edge case differently

        ndc = clip_space[:3] / clip_space[3]

        # Convert NDC to screen coordinates
        screen_x = int((ndc[0] + 1) / 2 * self.screen_width)
        screen_y = int((1 - (ndc[1] + 1) / 2) * self.screen_height)

        return (screen_x, screen_y)


def look_at(eye: np.ndarray, target: np.ndarray, up: np.ndarray) -> np.ndarray:
    forward = target - eye
    forward /= np.linalg.norm(forward)
    side = np.cross(forward, up)
    side /= np.linalg.norm(side)
    up_corrected = np.cross(side, forward)
    M = np.eye(4)
    M[0, :3] = side
    M[1, :3] = up_corrected
    M[2, :3] = -forward
    T = np.eye(4)
    T[:3, 3] = -eye
    return M @ T


def perspective(fov: float, aspect: float, near: float, far: float) -> np.ndarray:
    f = 1.0 / np.tan(np.radians(fov) / 2)
    M = np.zeros((4, 4))
    M[0, 0] = f / aspect
    M[1, 1] = f
    M[2, 2] = (far + near) / (near - far)
    M[2, 3] = (2 * far * near) / (near - far)
    M[3, 2] = -1
    return M


# ---- GameObject and Component System ----
class GameObject:
    def __init__(
        self,
        pipeline: FramePipeline[EngineFrameData],
        name: str = "GameObject",
        position: Tuple[int, int] = (0, 0),
        components: List["Component"] = [],
    ):
        self.name = name
        self.position = list(position)
        self.components: List[Component] = []
        self.pipeline = pipeline
        for comp in components:
            self.add_component(comp)
        pipeline.attach(FrameListener, lambda frame: self.update(frame.data))

    def add_component(self, component: "Component"):
        if not isinstance(component, Component):
            raise TypeError("Must add a Component subclass")
        component.game_object = self
        self.components.append(component)
        component.awake()

    def remove_component(self, component: "Component"):
        if component in self.components:
            component.on_disable()
            self.components.remove(component)
            component.game_object = None

    def find_component(self, component_type: Type[T]) -> Optional[T]:
        for comp in self.components:
            if isinstance(comp, component_type):
                return comp
        return None

    def update(self, frame: EngineFrameData):
        if frame.code == EngineCode.COMPONENT_TICK:
            for comp in self.components:
                comp.update()
                comp.render(frame.sdl, frame.camera)

    def render(self, sdl: SDLWrapper, camera: Optional[Union[Camera, Camera3D]] = None):
        for comp in self.components:
            comp.render(sdl, camera)


class Component:
    def __init__(self):
        self.game_object: Optional[GameObject] = None

    def awake(self):
        pass

    def on_enable(self):
        pass

    def on_disable(self):
        pass

    def update(self):
        pass

    def render(self, sdl: SDLWrapper, camera: Optional[Union[Camera, Camera3D]] = None):
        pass


# ---- 2D Transform and SpriteRenderer ----
class Transform(Component):
    def __init__(
        self,
        position: Tuple[float, float] = (0.0, 0.0),
        rotation: float = 0.0,
        scale: Tuple[float, float] = (1.0, 1.0),
    ):
        super().__init__()
        self.position = np.array(position, dtype=float)
        self.rotation = rotation
        self.scale = np.array(scale, dtype=float)
        self._matrix = None

    def set_position(self, position: Tuple[float, float]):
        self.position = np.array(position, dtype=float)
        self._matrix = None

    def set_rotation(self, rotation: float):
        self.rotation = rotation
        self._matrix = None

    def set_scale(self, scale: Tuple[float, float]):
        self.scale = np.array(scale, dtype=float)
        self._matrix = None

    def get_matrix(self) -> np.ndarray:
        if self._matrix is None:
            translation_matrix = np.array(
                [[1, 0, self.position[0]], [0, 1, self.position[1]], [0, 0, 1]],
                dtype=float,
            )
            rotation_matrix = np.array(
                [
                    [
                        np.cos(np.radians(self.rotation)),
                        -np.sin(np.radians(self.rotation)),
                        0,
                    ],
                    [
                        np.sin(np.radians(self.rotation)),
                        np.cos(np.radians(self.rotation)),
                        0,
                    ],
                    [0, 0, 1],
                ],
                dtype=float,
            )
            scale_matrix = np.array(
                [[self.scale[0], 0, 0], [0, self.scale[1], 0], [0, 0, 1]], dtype=float
            )
            self._matrix = translation_matrix @ rotation_matrix @ scale_matrix
        return self._matrix

    def world_to_local(self, world_point: Tuple[float, float]) -> np.ndarray:
        wp = np.array([world_point[0], world_point[1], 1], dtype=float)
        inv = np.linalg.inv(self.get_matrix())
        local = inv @ wp
        return local[:2]

    def local_to_world(self, local_point: Tuple[float, float]) -> np.ndarray:
        lp = np.array([local_point[0], local_point[1], 1], dtype=float)
        world = self.get_matrix() @ lp
        return world[:2]

    def get_global_position(self) -> np.ndarray:
        return self.position

    def get_global_rotation(self) -> float:
        return self.rotation

    def get_global_scale(self) -> np.ndarray:
        return self.scale


class SpriteRenderer(Component):
    def __init__(self):
        super().__init__()

    def awake(self):
        if self.game_object is None:
            raise RuntimeError("SpriteRenderer must be attached to a GameObject.")

    def render(self, sdl: SDLWrapper, camera: Optional[Union[Camera, Camera3D]] = None):
        if self.game_object is None:
            return
        transform = self.game_object.find_component(Transform)
        if transform is None:
            raise RuntimeError("SpriteRenderer requires a Transform component.")
        # if camera:
        # screen_x, screen_y = camera.world_to_screen(tuple(transform.get_global_position()))
        # else:
        screen_x, screen_y = transform.get_global_position()
        sdl.draw_rect(int(screen_x), int(screen_y), 100, 100, 255, 0, 0)


# ---- 3D Transform, Mesh, and MeshRenderer ----
class Transform3D(Component):
    def __init__(
        self,
        position: Tuple[float, float, float] = (0, 0, 0),
        rotation: Tuple[float, float, float] = (0, 0, 0),
        scale: Tuple[float, float, float] = (1, 1, 1),
    ):
        super().__init__()
        self.position = np.array(position, dtype=float)
        self.rotation = np.array(rotation, dtype=float)
        self.scale = np.array(scale, dtype=float)
        self._matrix = None

    def get_matrix(self) -> np.ndarray:
        if self._matrix is None:
            T = np.eye(4)
            T[:3, 3] = self.position
            pitch, yaw, roll = np.radians(self.rotation)
            Rx = np.array(
                [
                    [1, 0, 0, 0],
                    [0, np.cos(pitch), -np.sin(pitch), 0],
                    [0, np.sin(pitch), np.cos(pitch), 0],
                    [0, 0, 0, 1],
                ]
            )
            Ry = np.array(
                [
                    [np.cos(yaw), 0, np.sin(yaw), 0],
                    [0, 1, 0, 0],
                    [-np.sin(yaw), 0, np.cos(yaw), 0],
                    [0, 0, 0, 1],
                ]
            )
            Rz = np.array(
                [
                    [np.cos(roll), -np.sin(roll), 0, 0],
                    [np.sin(roll), np.cos(roll), 0, 0],
                    [0, 0, 1, 0],
                    [0, 0, 0, 1],
                ]
            )
            R = Rz @ Ry @ Rx
            S = np.eye(4)
            S[0, 0] = self.scale[0]
            S[1, 1] = self.scale[1]
            S[2, 2] = self.scale[2]
            self._matrix = T @ R @ S
        return self._matrix

    def world_to_local(self, world_point: Tuple[float, float, float]) -> np.ndarray:
        point = np.array([*world_point, 1.0])
        inv = np.linalg.inv(self.get_matrix())
        local = inv @ point
        return local[:3]

    def local_to_world(self, local_point: Tuple[float, float, float]) -> np.ndarray:
        point = np.array([*local_point, 1.0])
        world = self.get_matrix() @ point
        return world[:3]


class Mesh:
    def __init__(
        self,
        vertices: List[Tuple[float, float, float]],
        indices: List[Tuple[int, int, int]],
    ):
        self.vertices = np.array(vertices, dtype=float)
        self.indices = indices


class MeshRenderer(Component):
    def __init__(
        self,
        mesh: Mesh,
        color: Tuple[int, int, int] = (255, 255, 255),
        material: Optional["Material"] = None,
        rotation_offset: Tuple[float, float, float] = (0.0, 0.0, 0.0),
    ):
        """
        :param mesh: The mesh to render.
        :param color: The color to use for drawing (used if no material/shader is provided).
        :param material: Optional material information.
        :param rotation_offset: An extra (pitch, yaw, roll) rotation (in degrees) to be applied on top of the GameObject's Transform3D rotation.
        """
        super().__init__()
        self.mesh = mesh
        self.color = color
        self.material = material
        self.rotation_offset = rotation_offset

    def render(self, sdl: SDLWrapper, camera: Optional[Union[Camera, Camera3D]] = None):
        if self.game_object is None:
            return

        transform3d: Transform3D = self.game_object.find_component(Transform3D)
        if transform3d is None:
            raise RuntimeError("MeshRenderer requires a Transform3D component.")

        if camera is None or not isinstance(camera, Camera3D):
            logger.warning("No Camera3D provided for MeshRenderer.")
            return

        aspect = sdl.get_width() / sdl.get_height()
        view_matrix = camera.get_view_matrix()
        proj_matrix = camera.get_projection_matrix(aspect)

        T = np.eye(4)
        T[:3, 3] = transform3d.position

        pitch, yaw, roll = np.radians(transform3d.rotation)
        Rx = np.array(
            [
                [1, 0, 0, 0],
                [0, np.cos(pitch), -np.sin(pitch), 0],
                [0, np.sin(pitch), np.cos(pitch), 0],
                [0, 0, 0, 1],
            ]
        )
        Ry = np.array(
            [
                [np.cos(yaw), 0, np.sin(yaw), 0],
                [0, 1, 0, 0],
                [-np.sin(yaw), 0, np.cos(yaw), 0],
                [0, 0, 0, 1],
            ]
        )
        Rz = np.array(
            [
                [np.cos(roll), -np.sin(roll), 0, 0],
                [np.sin(roll), np.cos(roll), 0, 0],
                [0, 0, 1, 0],
                [0, 0, 0, 1],
            ]
        )
        R = Rz @ Ry @ Rx

        if self.rotation_offset != (0.0, 0.0, 0.0):
            opitch, oyaw, oroll = np.radians(self.rotation_offset)
            ORx = np.array(
                [
                    [1, 0, 0, 0],
                    [0, np.cos(opitch), -np.sin(opitch), 0],
                    [0, np.sin(opitch), np.cos(opitch), 0],
                    [0, 0, 0, 1],
                ]
            )
            ORy = np.array(
                [
                    [np.cos(oyaw), 0, np.sin(oyaw), 0],
                    [0, 1, 0, 0],
                    [-np.sin(oyaw), 0, np.cos(oyaw), 0],
                    [0, 0, 0, 1],
                ]
            )
            ORz = np.array(
                [
                    [np.cos(oroll), -np.sin(oroll), 0, 0],
                    [np.sin(oroll), np.cos(oroll), 0, 0],
                    [0, 0, 1, 0],
                    [0, 0, 0, 1],
                ]
            )
            R_offset = ORz @ ORy @ ORx
            R = R @ R_offset

        # Scale matrix.
        S = np.eye(4)
        S[0, 0] = transform3d.scale[0]
        S[1, 1] = transform3d.scale[1]
        S[2, 2] = transform3d.scale[2]

        model_matrix = T @ R @ S

        for tri in self.mesh.indices:
            pts = []
            for idx in tri:
                if idx >= len(self.mesh.vertices):
                    continue
                vertex = np.array([*self.mesh.vertices[idx], 1.0])
                clip_space = proj_matrix @ view_matrix @ model_matrix @ vertex
                if clip_space[3] == 0:
                    continue
                ndc = clip_space[:3] / clip_space[3]
                x_screen = (ndc[0] + 1) / 2 * sdl.get_width()
                y_screen = (1 - (ndc[1] + 1) / 2) * sdl.get_height()
                pts.append((int(x_screen), int(y_screen)))
            if len(pts) == 3:
                sdl.draw_line(pts[0][0], pts[0][1], pts[1][0], pts[1][1], *self.color)
                sdl.draw_line(pts[1][0], pts[1][1], pts[2][0], pts[2][1], *self.color)
                sdl.draw_line(pts[2][0], pts[2][1], pts[0][0], pts[0][1], *self.color)


# ---- Rigidbody (Simple Physics) ----
class Rigidbody(Component):
    def __init__(self, mass: float = 1.0):
        super().__init__()
        self.mass = mass
        self.velocity = np.array([0.0, 0.0, 0.0])
        self.acceleration = np.array([0.0, 0.0, 0.0])
        self.use_gravity = True

    def update(self):
        dt = 1 / 60.0
        if self.use_gravity:
            gravity = np.array([0.0, -9.81, 0.0])
            self.acceleration = gravity
        self.velocity += self.acceleration * dt
        transform3d: Transform3D = self.game_object.find_component(Transform3D)
        if transform3d:
            transform3d.position += self.velocity * dt


# ---- ScriptComponent for Custom Logic ----
class ScriptComponent(Component):
    def __init__(self):
        super().__init__()

    def update(self):
        pass


# ---- AudioManager Stub ----
class AudioManager:
    def __init__(self):
        self.sounds: Dict[str, Any] = {}

    def load_sound(self, name: str, filepath: str):
        self.sounds[name] = filepath

    def play_sound(self, name: str):
        if name in self.sounds:
            print(f"[Audio] Playing sound: {name}")
        else:
            print(f"[Audio] Sound not found: {name}")


# ---- Materials and Shaders (Stubbed) ----
class Shader:
    def __init__(self, vertex_code: str, fragment_code: str):
        self.vertex_code = vertex_code
        self.fragment_code = fragment_code


class Material:
    def __init__(
        self,
        shader: Optional[Shader] = None,
        color: Tuple[int, int, int] = (255, 255, 255),
    ):
        self.shader = shader
        self.color = color


# ---- Light Component ----
class Light(Component):
    def __init__(
        self,
        light_type: str = "directional",
        intensity: float = 1.0,
        color: Tuple[int, int, int] = (255, 255, 255),
    ):
        super().__init__()
        self.light_type = light_type
        self.intensity = intensity
        self.color = color
        self.direction = np.array([0.0, -1.0, 0.0])

    def update(self):
        pass

    def render(self, sdl: SDLWrapper, camera: Optional[Union[Camera, Camera3D]] = None):
        pass


# ---- ResourceManager ----
class ResourceManager:
    def __init__(self):
        self.textures: Dict[str, Any] = {}
        self.models: Dict[str, Any] = {}
        self.sounds: Dict[str, Any] = {}

    def load_texture(self, name: str, filepath: str):
        self.textures[name] = filepath

    def get_texture(self, name: str):
        return self.textures.get(name, None)

    def load_model(self, name: str, filepath: str):
        self.models[name] = filepath

    def get_model(self, name: str):
        return self.models.get(name, None)

    def load_sound(self, name: str, filepath: str):
        self.sounds[name] = filepath

    def get_sound(self, name: str):
        return self.sounds.get(name, None)


# =============================================================================
# UI System with Animation
# =============================================================================


# A simple Rect class for UI positioning.
class Rect:
    def __init__(self, x: int, y: int, w: int, h: int):
        self.x = x
        self.y = y
        self.w = w
        self.h = h


# UIElement represents a UI component that can be animated.
class UIElement:
    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        color: Tuple[int, int, int] = (200, 200, 200),
        opacity: float = 1.0,
        on_hover: Optional[Tuple[int, int, int]] = None,
    ):
        self.rect = Rect(x, y, width, height)
        self.color = color
        self.opacity = opacity
        self.visible = True
        self.animations: List[UIAnimation] = []
        self.on_hover = on_hover

    def update(self, dt: float, sdl: SDLWrapper):
        for anim in self.animations:
            anim.update(dt)
        self.animations = [anim for anim in self.animations if not anim.finished]

    def render(self, sdl: SDLWrapper):
        if self.visible:

            mouse_pos = sdl.getMousePosition()
            rect_x, rect_y, rect_w, rect_h = (
                self.rect.x,
                self.rect.y,
                self.rect.w,
                self.rect.h,
            )

            rect_vertices = [
                (rect_x, rect_y),
                (rect_x + rect_w, rect_y),
                (rect_x + rect_w, rect_y + rect_h),
                (rect_x, rect_y + rect_h),
            ]

            r, g, b = (
                self.on_hover
                if intersects(mouse_pos, rect_vertices) and self.on_hover
                else self.color
            )

            sdl.draw_rect(int(rect_x), int(rect_y), rect_w, rect_h, r, g, b)

    def add_animation(self, animation: "UIAnimation"):
        self.animations.append(animation)


# UIAnimation will tween a numeric property on a target object.
class UIAnimation:
    def __init__(
        self,
        target: Any,
        property_name: str,
        start_value: float,
        end_value: float,
        duration: float,
        easing: Optional[Callable[[float], float]] = None,
    ):
        self.target = target
        self.property_name = property_name
        self.start_value = start_value
        self.end_value = end_value
        self.duration = duration
        self.elapsed = 0.0
        self.finished = False
        self.easing = easing if easing is not None else (lambda t: t)

    def update(self, dt: float):
        if self.finished:
            return
        self.elapsed += dt
        t = min(self.elapsed / self.duration, 1.0)
        t_eased = self.easing(t)
        new_value = self.start_value + (self.end_value - self.start_value) * t_eased
        setattr(self.target, self.property_name, new_value)
        if t >= 1.0:
            self.finished = True


class UIButton(UIElement):
    def __init__(
        self,
        x: int,
        y: int,
        width: int,
        height: int,
        text_renderer: "TextRenderer",
        text: str = "",
        color: Tuple[int, int, int] = (200, 200, 255),
        on_hover: Optional[Tuple[int, int, int]] = (255, 0, 0),
        callback: Optional[Callable[[], None]] = None,
        text_color: Tuple[int, int, int] = (255, 255, 255),
        font_size: int = 24,
    ):
        """
        A UI button that executes a callback when clicked and displays text.

        :param x: X position of the button
        :param y: Y position of the button
        :param width: Button width
        :param height: Button height
        :param text_renderer: Shared text renderer to draw text
        :param text: Text to display on the button
        :param color: Default button color
        :param on_hover: Button color when hovered
        :param callback: Function to execute when clicked
        :param text_color: Color of the text
        :param font_size: Font size for the button text
        """
        super().__init__(x, y, width, height, color, on_hover=on_hover)
        self.callback = callback
        self.text_renderer = text_renderer  # Store reference to TextRenderer
        self.text = text
        self.text_color = text_color
        self.font_size = font_size

    def render(self, sdl: SDLWrapper):
        """Renders the button and its text."""
        if not self.visible:
            return

        # Determine button color (hover effect)
        mouse_pos = sdl.getMousePosition()
        rect_x, rect_y, rect_w, rect_h = (
            self.rect.x,
            self.rect.y,
            self.rect.w,
            self.rect.h,
        )
        rect_vertices = [
            (rect_x, rect_y),
            (rect_x + rect_w, rect_y),
            (rect_x + rect_w, rect_y + rect_h),
            (rect_x, rect_y + rect_h),
        ]
        r, g, b = self.on_hover if intersects(mouse_pos, rect_vertices) else self.color

        # Draw button rectangle
        sdl.fill_rect(rect_x, rect_y, rect_w, rect_h, r, g, b)

        # Draw text centered in the button
        text_width = self.text_renderer.get_text_width(self.text)
        text_height = self.text_renderer.get_font_height(self.text)

        text_x = rect_x + (rect_w - text_width) // 2
        text_y = rect_y + (rect_h - text_height) // 2

        self.text_renderer.draw_text(self.text, text_x, text_y, self.text_color)

    def update(self, dt: float, sdl: SDLWrapper):
        """Checks if the button was clicked and executes the callback."""
        mouse_pos = sdl.getMousePosition()
        mouse_pressed = sdl.is_mouse_button_down(bindings.SDL_BUTTON_LEFT)

        if (
            self.rect.x <= mouse_pos[0] <= self.rect.x + self.rect.w
            and self.rect.y <= mouse_pos[1] <= self.rect.y + self.rect.h
        ):
            if mouse_pressed and self.callback and sdl.is_window_focused():
                self.callback()


# UIManager holds and updates all UI elements.
class UIManager:
    def __init__(self):
        self.ui_elements: List[UIElement] = []

    def add_element(self, element: UIElement):
        self.ui_elements.append(element)

    def update(self, dt: float, sdl: SDLWrapper):
        for element in self.ui_elements:
            element.update(dt, sdl)

    def render(self, sdl: SDLWrapper):
        for element in self.ui_elements:
            element.render(sdl)


# Some common easing functions.
def ease_in_out_quad(t: float) -> float:
    if t < 0.5:
        return 2 * t * t
    else:
        return -1 + (4 - 2 * t) * t


class Engine(InternalEngine):
    def __init__(
        self,
        pipeline,
        event_pipeline,
        state_pipeline,
        window_title="Full Game Engine",
        width=1024,
        height=768,
    ):
        super().__init__(
            pipeline, event_pipeline, state_pipeline, window_title, width, height
        )
        self.scene_manager = SceneManager(self.sdl)
        self.input_manager = InputManager()
        self.ui_manager = UIManager()
        self.audio_manager = AudioManager()
        self.resource_manager = ResourceManager()
        self.last_time = time.time()
        self.input_manager.register_key_down(SDL_Scancode.Escape, self.quit)

    def handle_events(self):
        event = SDL_Event()
        while self.sdl.poll_event(event):
            if event.type == SDL_EventType.QUIT:
                self.quit()
            else:
                self.input_manager.process_event(event)

    def update(self):
        current_time = time.time()
        dt = current_time - self.last_time
        self.last_time = current_time
        frame_data = EngineFrameData(EngineCode.COMPONENT_TICK, self.sdl, self.camera)
        if self.scene_manager.current_scene:
            self.scene_manager.current_scene.update(frame_data, self.sdl)
        else:
            for game_object in self.game_objects:
                game_object.update(frame_data)

        self.ui_manager.update(dt, self.sdl)

    def override_render(self) -> None:
        pass

    def render(self, override: bool = False):
        if not override:
            self.sdl.clear_screen(0, 0, 0)
        if self.scene_manager.current_scene:
            self.scene_manager.current_scene.render(self.sdl, self.camera)
        else:
            for game_object in self.game_objects:
                game_object.render(self.sdl, self.camera)
        self.ui_manager.render(self.sdl)

        self.override_render()

        self.sdl.update_screen()


# ---- Scene Management ----
class Scene:
    def __init__(self, name: str):
        self.name = name
        self.game_objects: List[GameObject] = []
        self.ui_elements: List[UIElement] = []
        self.ambient_light = (50, 50, 50)

    def add_game_object(self, game_object: GameObject):
        self.game_objects.append(game_object)

    def remove_game_object(self, game_object: GameObject):
        self.game_objects.remove(game_object)

    def add_ui_element(self, element: UIElement):
        self.ui_elements.append(element)

    def update(self, frame_data: EngineFrameData, sdl: SDLWrapper):
        for obj in self.game_objects:
            obj.update(frame_data)
        # Assume a fixed dt for UI elements (or pass in a dt from engine)
        for ui in self.ui_elements:
            ui.update(1 / 60.0, sdl)

    def render(self, sdl: bindings.SDLWrapper, camera: Union[Camera, Camera3D]):
        for obj in self.game_objects:
            obj.render(sdl, camera)
        for ui in self.ui_elements:
            ui.render(sdl)


class SceneManager:
    def __init__(self, sdl: SDLWrapper):
        self.current_scene: Optional[Scene] = None
        self.scenes: Dict[str, Scene] = {}
        self.sdl: SDLWrapper = sdl

    def add_scene(self, scene: Scene):
        self.scenes[scene.name] = scene

    def load_scene(self, scene_name: str):
        if scene_name in self.scenes:
            self.current_scene = self.scenes[scene_name]
        else:
            print("Scene not found:", scene_name)

    def update(self, frame_data: EngineFrameData):
        if self.current_scene:
            self.current_scene.update(frame_data, self.sdl)

    def render(self, sdl: bindings.SDLWrapper, camera: Union[Camera, Camera3D]):
        if self.current_scene:
            self.current_scene.render(sdl, camera)


# ---- Input Manager ----
class InputManager:
    def __init__(self):
        self.key_down_callbacks: Dict[Any, Callable[[], None]] = {}
        self.key_up_callbacks: Dict[Any, Callable[[], None]] = {}

    def register_key_down(self, key, callback: Callable[[], None]):
        self.key_down_callbacks[key] = callback

    def register_key_up(self, key, callback: Callable[[], None]):
        self.key_up_callbacks[key] = callback

    def process_event(self, event: bindings.SDL_Event):
        if event.type == bindings.SDL_EventType.KEYDOWN:
            key = event.key.keysym.scancode
            if key in self.key_down_callbacks:
                self.key_down_callbacks[key]()
        # elif event.type == bindings.SDL_EventType.KEYUP:
        #     key = event.key.keysym.scancode
        #     if key in self.key_up_callbacks:
        #         self.key_up_callbacks[key]()


class TextRenderer:
    def __init__(self, sdl: SDLWrapper):
        self.sdl = sdl
        self.font = None  # Store the loaded font
        self.font_path = ""

    def load_font(self, path: str, size: int):
        """Loads a font. Returns True on success, False on failure."""
        self.font = self.sdl.load_font(path, size)
        self.font_path = path
        return self.font

    def set_font_size(self, size: int):
        """Sets the font size.  Reloads the font if necessary."""
        if self.font:
            if self.font_path != "":
                if self.load_font(self.font_path, size):  # Reload with new size
                    pass
                else:
                    print(f"Error changing font size to {size}")
            else:
                print("Error: Could not retrieve font path to resize.")
        else:
            self.font_size = size  # Set it for when the font is actually loaded

    def draw_text(self, text: str, x: int, y: int, color: Tuple[int, int, int]):
        """Draws text. Accepts RGB tuple."""
        if not self.font:
            print("Error: No font loaded. Call load_font() first.")
            return

        r, g, b = color  # No need for isinstance check as only RGB tuple is accepted.
        self.sdl.draw_text(text, x, y, r, g, b)

    def get_text_width(self, text: str) -> int:
        """Returns the width of the given text in pixels."""
        if not self.font:
            print("Error: No font loaded. Call load_font() first.")
            return 0
        return self.sdl.get_text_size(text).w

    def get_font_height(self, text) -> int:
        """Returns the height of the current font in pixels."""
        if not self.font:
            print("Error: No font loaded. Call load_font() first.")
            return 0
        return self.sdl.get_text_size(text).h
