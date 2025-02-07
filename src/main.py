import threading
import bindings  # Assuming this is your bindings module
import time
from engine import Engine, EngineCode, EngineFrameData, FramePipeline, GameObject, SpriteRenderer, Transform  # Your engine imports
from pipeline import Event, EventType, PipelineState, PipelineSupplier, StateData, frame_printer  # Your pipeline imports
import random

def main():
    event_pipe = FramePipeline[Event]("event_pipe")
    state_pipe = FramePipeline[StateData]("state_pipe")
    engine_pipe = FramePipeline[EngineFrameData]("engine_pipe")

    # state_pipe.attach(frame_printer(state_pipe))
    # event_pipe.attach(frame_printer(event_pipe))

    engine = Engine(engine_pipe, event_pipe, state_pipe)

    _get, _set = engine.manage(1).to_tuple()

    def tick():
        print(_get())
        _set(int(time.time()))
    engine.run(tick)

    event_pipe.close()
    state_pipe.close()

if __name__ == "__main__":
    main()
