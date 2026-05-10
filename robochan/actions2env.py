"""action2robot.py - the module that interfaces bewteen the action and the robot/drone"""
from __future__ import annotations
import threading
import traceback
from queue import Empty

from .environment import Environment
from .actions_queue import ActionsQueue, Action
from .types import ActionsFn
from .utils import logger

TIMEOUT_S = 0.01

class Actions2Environment(threading.Thread):
    """Interface defining the requirements of a robot (real, sym, mock) to receive  actions & apply them to the env"""
    def __init__(self, env: Environment, actions_queue: ActionsQueue, actions_fn: ActionsFn):
        threading.Thread.__init__(self, daemon=True)
        assert isinstance(actions_queue, ActionsQueue), f"queue must inherit ActionsQueue: {type(actions_queue)}"
        self.env = env
        self.actions_queue = actions_queue
        self.actions_fn = actions_fn

    def _fetch_actions(self) -> list[Action]:
        actions, timestamps = [], []
        try: # 1st is blocking, rest are non-blocking, so we don't use sleeps.
            action, ts = self.actions_queue.get(block=True, timeout=TIMEOUT_S)
            actions.append(action)
            timestamps.append(ts)
            while True:
                action, ts = self.actions_queue.get_nowait()
                actions.append(action)
                timestamps.append(ts)
        except Empty:
            pass

        if len(actions) > 0:
            msg = f"Processing {len(actions)} actions: "
            for action, ts in zip(actions, timestamps):
                msg += f"\n - {action} (ts: {ts})"
            logger.log_every_s(msg, "DEBUG", True)
        return actions

    def run(self):
        while self.env.is_running():
            try:
                actions = self._fetch_actions()
                if len(actions) == 0:
                    continue
                res = self.actions_fn(self.env, actions)
                if res is False:
                    logger.warning(f"Could not perform one or more actions: '{actions}'")
            except Exception as e:
                logger.error(f"Error {e}\nTraceback: {traceback.format_exc()}")
                break

        logger.debug(f"Stopping {self}. {self.env.is_running()=}")
