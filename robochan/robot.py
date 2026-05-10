"""robot.py - The basic Robot class that defines all the low-level wirings and should handle 95% of the cases"""
from typing import Callable
import threading
import time
from datetime import datetime
from .environment import Environment
from .data_channel import DataChannel
from .actions_queue import ActionsQueue
from .data_producer import DataProducer, RawDataProducer
from .controller import BaseController, Controller
from .actions2env import Actions2Environment
from .data_producers2channels import DataProducers2Channels
from .types import ActionsFn, ControllerFn
from .utils import ThreadGroup, ThreadStatus, logger, parsed_str_type

SLEEP_TIME = 1

def _make_status(status: dict[str, ThreadStatus], env: Environment, start_time: datetime) -> str:
    """Print a summary table of thread statuses after robot.run() completes."""
    duration = (datetime.now() - start_time).total_seconds()
    lines = [
        f"Robot ran for: {duration:.2f} seconds.",
        f"{'Thread':<35} {'Alive':<10} {'Exception':<50}",
        "-" * 90,
    ]

    for name, ts in status.items():
        exc_str = "-" if ts.exception is None else f"{type(ts.exception).__name__}: {str(ts.exception)}"
        lines.append(f"{name:<35} {str(ts.is_alive):<10} {exc_str:<50}")
    lines.append(f"Env: {parsed_str_type(env):<30} {str(env.is_running()):<10} {'-':<50}")
    lines.append("-" * 90 + "\n")
    return "\n".join(lines)

class Robot:
    """
    Robot class that interacts with an environment and has a single data channel and a single actions queue.
    The action_fn is the callback that converts generic actions to env-specific commands.
    """
    def __init__(self, env: Environment, data_channel: DataChannel, actions_queue: ActionsQueue, actions_fn: ActionsFn):
        self.env = env
        self.data_channel = data_channel
        self.actions_queue = actions_queue
        self.actions_fn = actions_fn

        # setup up at run() time
        self._data_producers: list[DataProducer] = []
        self._env2data: DataProducers2Channels | None = None
        self._controllers: dict[str, Controller] = {}
        self._actions2env = Actions2Environment(self.env, self.actions_queue, self.actions_fn)
        self._other_threads: dict[str, threading.Thread] = {} # e.g. maybe we want to start the env at the same time.

    def add_data_producer(self, data_producer: DataProducer):
        """Add a data producer (i.e. yolo, semantic, optical flow etc.) to this robot. Has access to 'raw' env data"""
        if not all(modality in self.data_channel.supported_types for modality in data_producer.modalities):
            raise ValueError(f"Unknown modality:\n-{data_producer.modalities=}\n-{self.data_channel.supported_types=}")
        self._data_producers.append(data_producer)

    def add_controller(self, controller: BaseController | ControllerFn, name: str | None = None):
        """Add a controller with optionally a name to this robot. If name is not set, it will be Controller-{i}"""
        if name is None:
            if isinstance(controller, BaseController) and not isinstance(controller, Controller):
                name = f"Controller: {parsed_str_type(controller)}"
            else:
                name = f"Controller-{len(self._controllers)}"
        if isinstance(controller, Callable):
            controller = Controller(self.data_channel, self.actions_queue, controller_fn=controller)
        assert isinstance(controller, BaseController), f"Expected 'robobase.Controller', got {type(controller)}"
        self._controllers[name] = controller

    def add_other_thread(self, thread: threading.Thread, name: str | None = None):
        """Add another thread to be spawned upon run() time. Useful to start the env at the same time for example"""
        assert isinstance(thread, threading.Thread), type(thread)
        name = name or f"Thread-{len(self._other_threads)}"
        self._other_threads[name] = thread

    def _setup_run(self):
        self.add_data_producer(RawDataProducer(self.env))
        assert len(self._controllers) > 0, "At least one controller expected. Use `robot.add_controller`"
        self._env2data = DataProducers2Channels(data_producers=self._data_producers, data_channels=[self.data_channel])

    def run(self, sleep_duration: float = SLEEP_TIME, print_status: bool = True) -> dict[str, ThreadStatus]:
        """start the robot's main loop which in turn starts all the threads: data producer + controllers + actuator"""
        start = datetime.now()
        self._setup_run()
        tg = ThreadGroup({
            "env2data": self._env2data,
            **self._controllers,
            **self._other_threads,
            "actions2env": self._actions2env,
        }).start()
        logger.info(f"Started threads: \n{tg}")

        try:
            while not tg.is_any_dead() and self.env.is_running():
                time.sleep(sleep_duration)
        finally:
            logger.debug(f"Joining threads: \n{tg}")
            res = tg.join(timeout=sleep_duration)
            if print_status:
                logger.info(_make_status(res, self.env, start))

            return res # pylint: disable=lost-exception return-in-finally
