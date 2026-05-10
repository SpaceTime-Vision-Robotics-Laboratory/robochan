"""replay_actions_queue.py -- Extends an ActionsQueue with replay abilities from an older run"""
from datetime import datetime
from pathlib import Path
from robochan import ActionsQueue, Action
from robochan.utils import load_npz_as_dict

class ReplayActionsQueue(ActionsQueue):
    """Extends an ActionsQueue with replay abilities from an older run"""
    def __init__(self, path: Path, mode: str, *args, **kwargs):
        assert mode in ("online", "offline"), mode
        super().__init__(*args, **kwargs)
        self.path = path
        self.mode = mode

        self._actions = self._build_actions()
        self._current_ix = 0

    def get(self, *args, **kwargs) -> tuple[Action, datetime]:
        if self._current_ix == len(self._actions):
            raise RuntimeError(f"ReplayActionsQueue depleeted (#actions: {len(self._actions)})")
        replay_action, replay_ts = self._actions[self._current_ix]
        self._current_ix += 1
        if self.mode == "online":
            action, action_ts = super().get(*args, **kwargs)
            if action != replay_action:
                raise ValueError(f"{action=} vs {replay_action=} mismatch at index={self._current_ix-1} ({replay_ts=})")
            return action, action_ts
        else: # mode == "offline"
            return replay_action, replay_ts

    def put(self, action: Action, data_ts: datetime | None, *args, **kwargs):
        assert self.mode == "online", "Can only add new actions (from controllers) if mode=='online'"
        super().put(action, data_ts, *args, **kwargs)

    def _build_actions(self) -> list[tuple[Action, datetime]]:
        assert self.path.exists(), self.path
        paths = sorted(self.path.iterdir(), key=lambda p: p.name)
        assert len(paths) > 0, f"No actions provided in '{self.path}'"
        res = [tuple(load_npz_as_dict(path).values()) for path in paths] # list of (action, action_ts) tuples
        assert all(len(a) == 2 for a in res), [(a, len(a)) for a in res]
        return res

    def __len__(self):
        return len(self._actions) - self._current_ix
