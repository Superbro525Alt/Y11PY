import threading
import bindings  # Assuming this is your bindings module
import time
from engine import Camera3D, Engine, EngineCode, EngineFrameData, FramePipeline, FullGameEngine, GameObject, Mesh, MeshRenderer, Rigidbody, Scene, ScriptComponent, SpriteRenderer, Transform, Transform3D, UIAnimation, UIElement, ease_in_out_quad  # Your engine imports
from pipeline import Event, EventType, ManagedState, PipelineState, PipelineSupplier, StateData, frame_printer  # Your pipeline imports
import random
from network import BaseNetworkObject, Client, EchoNetworkObject, PacketType, Server, Packet
from util import logger
import perftester as pt 

def _client():
    engine_pipe = FramePipeline[EngineFrameData]("engine_pipe")
    state_pipe = FramePipeline[StateData]("state_pipe")
    event_pipe = FramePipeline[Event]("event_pipe")

    engine = FullGameEngine(engine_pipe, event_pipe, state_pipe,
                            window_title="Full Game Engine", width=1024, height=768)

    # Set up a 3D camera.
    camera3d = Camera3D(position=(0, 0, 10), target=(0, 0, 0), fov=60, near=0.1, far=1000)
    engine.set_camera(camera3d)

    # Define a cube mesh.
    cube_vertices = [
         (-1, -1, -1),
         ( 1, -1, -1),
         ( 1,  1, -1),
         (-1,  1, -1),
         (-1, -1,  1),
         ( 1, -1,  1),
         ( 1,  1,  1),
         (-1,  1,  1)
    ]
    cube_indices = [
         (0, 1, 2), (0, 2, 3),
         (4, 5, 6), (4, 6, 7),
         (0, 1, 5), (0, 5, 4),
         (2, 3, 7), (2, 7, 6),
         (1, 2, 6), (1, 6, 5),
         (0, 3, 7), (0, 7, 4)
    ]
    cube_mesh = Mesh(cube_vertices, cube_indices)

    # Define a Cube GameObject that rotates.
    class Cube(GameObject):
         def __init__(self, pipeline, name="Cube"):
             super().__init__(pipeline, name=name)
             self.add_component(Transform3D(position=(0, 0, 0), rotation=(30, 45, 0), scale=(1, 1, 1)))
             self.add_component(MeshRenderer(cube_mesh, color=(0, 255, 0)))
             self.add_component(Rigidbody(mass=1.0))
             self.add_component(ScriptComponent())
         def update(self, frame: EngineFrameData):
             transform3d: Transform3D = self.find_component(Transform3D)
             if transform3d:
                transform3d.rotation[1] += 1 
                transform3d.rotation[2] += 1
             super().update(frame)

    # Create a main scene.
    main_scene = Scene("MainScene")
    cube_object = Cube(engine_pipe)
    main_scene.add_game_object(cube_object)

    ui_panel = UIElement(x=50, y=50, width=300, height=150, color=(100, 100, 250), opacity=0.0)
    fade_in = UIAnimation(target=ui_panel, property_name="opacity", start_value=0.0, end_value=1.0, duration=2.0, easing=ease_in_out_quad)
    ui_panel.add_animation(fade_in)
    initial_x = ui_panel.rect.x
    ui_panel.rect.x = -ui_panel.rect.w  
    slide_in = UIAnimation(target=ui_panel.rect, property_name="x", start_value=-ui_panel.rect.w, end_value=initial_x, duration=2.0, easing=ease_in_out_quad)
    ui_panel.add_animation(slide_in)
    main_scene.add_ui_element(ui_panel)

    # Register and load the scene.
    engine.scene_manager.add_scene(main_scene)
    engine.scene_manager.load_scene("MainScene")

    # Run the engine.
    engine.run(lambda: None)

def _server():
    pass

if __name__ == "__main__":
    
