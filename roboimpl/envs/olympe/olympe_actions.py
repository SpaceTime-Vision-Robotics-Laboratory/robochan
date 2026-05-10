"""olympe_actions.py - defines all the supported actions of an olympe drone from our generic ones to the drone's"""
import threading
from olympe.messages.ardrone3.Piloting import Landing, TakeOff
from olympe.messages import gimbal

from robochan import Action
from roboimpl.utils import logger
from .olympe_env import OlympeEnv

# the list of all supported actions from our generic ones to the drone's internal ones.
OLYMPE_ACTION_NAMES = [
    "DISCONNECT", "LIFT", "LAND", "PILOTING", "GIMBAL_UP", "GIMBAL_DOWN", "GIMBAL_ABSOLUTE"
]

def olympe_action_fn(env: OlympeEnv, action: Action) -> bool:
    """non-batch variant as olympe doesn't support ootb batching"""
    drone = env.drone
    if action.name == "DISCONNECT":
        drone.streaming.stop()
        return True

    if action.name == "LIFT":
        return drone(TakeOff()).wait().success()

    if action.name == "LAND":
        return drone(Landing()).wait().success()

    if action.name == "PILOTING":
        roll, pitch, yaw, gaz, piloting_time = action.parameters
        if any(not -100 <= v <= 100 for v in [roll, pitch, yaw, gaz]):
            logger.error(f"Velocity not in [-100:100]. Got: {action}")
            return False
        return drone.piloting(roll, pitch, yaw, gaz, piloting_time)

    if action.name == "GIMBAL_ABSOLUTE":
        gimbal_kwargs = {"gimbal_id": 0, "control_mode": "position", "yaw_frame_of_reference": "none", "yaw": 0,
                         "roll_frame_of_reference": "none", "roll": 0, "pitch_frame_of_reference": "absolute"}
        drone(gimbal.set_target(pitch=action.parameters[0], **gimbal_kwargs))
        return True

    # drone.piloting() does this for us, but for gimbal, we do it ourselves (blocking for now).
    velocity, piloting_time = action.parameters
    if not -100 <= velocity <= 100:
        logger.error(f"Velocity not in [-100:100]. Got: {velocity}")
        return False

    # gimbal stuff
    gimbal_kwargs = {"gimbal_id": 0, "control_mode": "velocity", "yaw_frame_of_reference": "none", "yaw": 0,
                     "roll_frame_of_reference": "none", "roll": 0, "pitch_frame_of_reference": "absolute"}
    if action.name == "GIMBAL_UP":
        drone(gimbal.set_target(pitch=velocity / 100, **gimbal_kwargs)) # pitch is in [-1:1] for this API
        threading.Timer(piloting_time, lambda: drone(gimbal.set_target(pitch=0, **gimbal_kwargs))).start()
        return True
    if action.name == "GIMBAL_DOWN":
        drone(gimbal.set_target(pitch=-velocity / 100, **gimbal_kwargs)) # pitch is in [-1:1] for this API
        threading.Timer(piloting_time, lambda: drone(gimbal.set_target(pitch=0, **gimbal_kwargs))).start()
        return True

    return False

def olympe_actions_fn(env: OlympeEnv, actions: list[Action]) -> bool:
    """the actions callback from generic actions to drone-specific ones. Note: all move acts are in (velocity, time)"""
    all_good = True
    for action in actions:
        all_good = all_good and olympe_action_fn(env, action)
    return all_good
