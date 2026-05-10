"""actions_queue.py - thread-safe queue composition with support for robobase generic actions"""
from queue import Queue
from datetime import datetime

from .action import Action
from .utils import DataStorer, logger

QUEUE_DEFAULT_MAX_SIZE = 20 # needed so .put() doesn't grow the queue indefinitely

class ActionsQueue:
    """Interface defining the actions understandable by a drone and the application. Queue must be thread-safe!"""
    def __init__(self, action_names: list[str], queue: Queue | None = None):
        assert len(action_names) > 0, "cannot have an empty list of actions"
        assert all(isinstance(action_name, str) for action_name in action_names), action_names
        self.queue = queue or Queue(maxsize=QUEUE_DEFAULT_MAX_SIZE)
        self.action_names = action_names

    def put(self, action: Action, data_ts: datetime | None, *args, **kwargs):
        """
        Put an action into the queue. data_ts is the ts of the data that produced the action or None (i.e. kb).
        args and kwargs are passed to the queue as we can have different queue implementations (i.e. priority queue).
        """
        assert isinstance(action, Action), type(action)
        assert action.name in self.action_names, f"{action} not in {self.action_names}"
        action_ts = datetime.now()
        logger.log_every_s(f"Got action (action_ts='{action_ts}'): {action} (#queue: {len(self)})", "DEBUG", True)

        if (storer := DataStorer.get_instance()) is not None:
            item = {"action": action, "data_ts": None if data_ts is None else data_ts.isoformat()} # correlate act-data
            storer.push(item=item, tag="ActionsQueue", timestamp=action_ts)

        self.queue.put((action, action_ts), *args, **kwargs)

    def get(self, *args, **kwargs) -> tuple[Action, datetime]:
        """Remove and return an item from the queue"""
        return self.queue.get(*args, **kwargs)

    def get_nowait(self, *args, **kwargs) -> tuple[Action, datetime]:
        """Remove and return an item from the queue without waiting"""
        return self.queue.get_nowait(*args, **kwargs)

    def __len__(self):
        return self.queue.qsize()

    def __repr__(self):
        return f"[ActionsQueue] Actions: {self.action_names} ({len(self.action_names)}). Size: {len(self)}"
