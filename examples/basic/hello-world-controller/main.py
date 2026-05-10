#!/usr/bin/env python3
"""basic minimal example to create and env, a data channel/actions queue and the middle part: dp, controller etc."""
import threading
from copy import deepcopy
from datetime import datetime
from robochan import Robot, Environment, DataChannel, ActionsQueue, DataItem, Action
from robochan.utils import wait_and_clear

TARGET = "helloworld"

class BasicEnv(Environment):
    """minimal environment"""
    def __init__(self):
        super().__init__()
        self._state = []
        self._lock = threading.Lock()
        self.data_ready.set()
    def push(self, action):
        """updates the state of the env in a thread-safe way"""
        with self._lock:
            self._state.append(action)
        self.data_ready.set()
    def is_running(self) -> bool:
        return len(self._state) != len(TARGET)
    def get_state(self) -> dict:
        wait_and_clear(self.data_ready)
        with self._lock:
            return {"ts": datetime.now().isoformat(), "state": deepcopy(self._state)} # important to deepcopy :)
    def get_modalities(self) -> list[str]:
        return ["ts", "state"]

def controller_fn(data: dict[str, DataItem]) -> list[Action]:
    """Basic controller function. Returns the next character given the current state, i.e. push 'e' if state==['h']"""
    match "".join(data["state"]):
        case "": return [Action("h")]
        case "h": return [Action("e")]
        case "he": return [Action("l")]
        case "hel": return [Action("l")]
        case "hell": return [Action("o")]
        case "hello": return [Action("w")]
        case "hellow": return [Action("o")]
        case "hellowo": return [Action("r")]
        case "hellowor": return [Action("l")]
        case "helloworl": return [Action("d")]
        case "helloworld": return []
    raise ValueError(data["state"])

def main():
    """main fn"""
    env = BasicEnv()
    data_channel = DataChannel(supported_types=["ts", "state"], eq_fn=lambda a, b: a["state"] == b["state"])
    actions_queue = ActionsQueue(action_names=[chr(x) for x in range(ord("a"), ord("z") + 1)]) # from 'a' to 'z'

    robot = Robot(env, data_channel, actions_queue, actions_fn=lambda env, acts: [env.push(act.name) for act in acts])
    robot.add_controller(controller=controller_fn)

    robot.run()
    data_channel.close()
    print(f"Final state: '{''.join(env._state)}'") # pylint: disable=protected-access
    assert "".join(env._state) == TARGET, env._state # pylint: disable=protected-access

if __name__ == "__main__":
    main()
