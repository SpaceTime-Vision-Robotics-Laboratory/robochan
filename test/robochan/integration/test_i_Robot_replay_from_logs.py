#!/usr/bin/env python3
"""basic minimal example to create and env, a data channel/actions queue and the middle part: dp, controller etc."""
import shutil
import threading
from pathlib import Path
from copy import deepcopy
from datetime import datetime
import pytest
import numpy as np
from robochan import Robot, Environment, DataChannel, ActionsQueue, Action, DataItem
from robochan.replay import ReplayDataProducer, ReplayActionsQueue
from robochan.utils import wait_and_clear, DataStorer, logger

TARGET = "helloworld"

class BasicEnv(Environment):
    """minimal environment"""
    def __init__(self):
        super().__init__()
        self._state = []
        self._lock = threading.Lock()
        self.data_ready.set() # first data is available from the beginning
    def push(self, action):
        """updates the state of the env in a thread-safe way"""
        with self._lock:
            # breakpoint()
            self._state.append(action)
        self.data_ready.set() # upon pushing, we signal that data is ready
    def is_running(self) -> bool:
        return len(self._state) != len(TARGET)
    def get_state(self) -> dict:
        wait_and_clear(self.data_ready) # you can only get the data once from the env: wait for 'green' light + clear.
        with self._lock:
            return {"ts": datetime.now().isoformat(), "state": deepcopy(self._state)} # important to deepcopy :)
    def get_modalities(self) -> list[str]:
        return ["ts", "state"]

def test_i_Robot_replay_from_logs(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env = BasicEnv()
    monkeypatch.setenv("ROBOCHAN_STORE_LOGS", "2")
    logger.get_file_handler().file_path = tmp_path / "logs.txt"
    shutil.rmtree(tmp_path, ignore_errors=True)
    data_channel = DataChannel(supported_types=["ts", "state"], eq_fn=lambda a, b: a["state"] == b["state"])
    actions_queue = ActionsQueue(action_names=[chr(x) for x in range(ord("a"), ord("z") + 1)]) # from 'a' to 'z'

    robot = Robot(env, data_channel, actions_queue, actions_fn=lambda env, acts: [env.push(act.name) for act in acts])
    # push 'h' if env._state==[], 'e' if env._state==['h'] and so on until helloworld
    robot.add_controller(lambda data: [Action(TARGET[len(data["state"])])] if len(data["state"]) < len(TARGET) else [])

    robot.run()
    data_channel.close()
    print(f"Final state: '{''.join(env._state)}'") # pylint: disable=protected-access
    assert "".join(env._state) == TARGET # pylint: disable=protected-access

    DataStorer.get_instance().close()

    # Load Data .npz files and compare states
    data_files = sorted(list((tmp_path / "DataChannel").iterdir()), key=lambda p: p.name)
    data = [np.load(x, allow_pickle=True) for x in data_files]
    for i in range(len(data)):
        assert "".join(data[i]["state"]) == TARGET[0:i]

    # Load Actions .npz files and compare states
    actions_files = sorted(list((tmp_path / "ActionsQueue").iterdir()), key=lambda p: p.name)
    actions = [np.load(x, allow_pickle=True) for x in actions_files]
    for i in range(len(actions)):
        assert actions[i]["action"].item().name == TARGET[i], (actions[i], TARGET[i])
        assert actions[i]["data_ts"].item() == data_files[i].stem

def test_i_Robot_replay_from_logs_ReplayDataProducer_ReplayActionsQueue(tmp_path: Path,
                                                                        monkeypatch: pytest.MonkeyPatch):
    """this test is basically the same as test_i_Robot_replay_from_logs but via the Replay classes"""
    env = BasicEnv()
    monkeypatch.setenv("ROBOCHAN_STORE_LOGS", "2")
    logger.get_file_handler().file_path = tmp_path / "logs.txt"
    shutil.rmtree(tmp_path, ignore_errors=True)
    data_channel = DataChannel(supported_types=["ts", "state"], eq_fn=lambda a, b: a["state"] == b["state"])
    actions_queue = ActionsQueue(action_names := [chr(x) for x in range(ord("a"), ord("z") + 1)]) # from 'a' to 'z'

    robot = Robot(env, data_channel, actions_queue, actions_fn=lambda env, acts: [env.push(act.name) for act in acts])
    # push 'h' if env._state==[], 'e' if env._state==['h'] and so on until helloworld
    robot.add_controller(lambda data: [Action(TARGET[len(data["state"])])] if len(data["state"]) < len(TARGET) else [])

    robot.run()
    data_channel.close()
    print(f"Final state: '{''.join(env._state)}'") # pylint: disable=protected-access
    assert "".join(env._state) == TARGET # pylint: disable=protected-access

    DataStorer.get_instance().close()

    # just read the data that was created via the data channel
    replay_data_producer = ReplayDataProducer(tmp_path / "DataChannel", prefix="replay_")
    for i in range(len(replay_data_producer._data)):
        data = replay_data_producer.produce()
        assert "".join(data["replay_state"]) == TARGET[0:i]

    replay_actions_queue = ReplayActionsQueue(tmp_path / "ActionsQueue", mode="offline", action_names=action_names)
    for i in range(len(replay_actions_queue)):
        action, _ = replay_actions_queue.get()
        assert action.name == TARGET[i], action
    with pytest.raises(RuntimeError, match="ReplayActionsQueue depleeted"):
        replay_actions_queue.get()

def test_i_Robot_replay_from_logs_offline_exception(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """this mostly makes sure that we cannot push() in ReplaActionsQueue mode='offline'"""
    env = BasicEnv()
    monkeypatch.setenv("ROBOCHAN_STORE_LOGS", "2")
    logger.get_file_handler().file_path = tmp_path / "logs.txt"
    shutil.rmtree(tmp_path, ignore_errors=True)
    data_channel = DataChannel(supported_types=["ts", "state"], eq_fn=lambda a, b: a["state"] == b["state"])
    actions_queue = ActionsQueue(action_names := [chr(x) for x in range(ord("a"), ord("z") + 1)]) # from 'a' to 'z'

    robot = Robot(env, data_channel, actions_queue, actions_fn=lambda env, acts: [env.push(act.name) for act in acts])
    # push 'h' if env._state==[], 'e' if env._state==['h'] and so on until helloworld
    robot.add_controller(lambda data: [Action(TARGET[len(data["state"])])] if len(data["state"]) < len(TARGET) else [])

    robot.run()
    data_channel.close()
    print(f"Final state: '{''.join(env._state)}'") # pylint: disable=protected-access
    assert "".join(env._state) == TARGET # pylint: disable=protected-access

    DataStorer.get_instance().close()

    def replay_controller_fn(data: dict[str, DataItem]) -> list[Action]:
        if len(data["state"]) == len(TARGET):
            return []
        assert data["state"] == data["replay_state"].tolist(), (data["state"], data["replay_state"])
        return [Action(TARGET[len(data["state"])])]

    # just read the data that was created via the data channel
    print("="*80)
    monkeypatch.setenv("ROBOCHAN_STORE_LOGS", "0")
    replay_env = BasicEnv()
    print(f"Start state: '{''.join(replay_env._state)}'") # pylint: disable=protected-access
    replay_data_channel = DataChannel(supported_types=["ts", "state", "replay_ts", "replay_state"],
                                      eq_fn=lambda a, b: a["state"] == b["state"])
    replay_data_producer = ReplayDataProducer(tmp_path / "DataChannel", prefix="replay_")
    replay_actions_queue = ReplayActionsQueue(tmp_path / "ActionsQueue", mode="offline", action_names=action_names)
    robot = Robot(replay_env, replay_data_channel, replay_actions_queue,
                  actions_fn=lambda env, acts: [env.push(act.name) for act in acts])
    robot.add_data_producer(replay_data_producer)
    robot.add_controller(replay_controller_fn)

    res = robot.run()
    replay_data_channel.close()
    print(f"Final state: '{''.join(replay_env._state)}'") # pylint: disable=protected-access
    assert "".join(replay_env._state) == TARGET # pylint: disable=protected-access
    assert res["Controller-0"].exception.__str__() == "Can only add new actions (from controllers) if mode=='online'"

def test_i_Robot_replay_from_logs_online_compare(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    env = BasicEnv()
    monkeypatch.setenv("ROBOCHAN_STORE_LOGS", "2")
    logger.get_file_handler().file_path = tmp_path / "logs.txt"
    shutil.rmtree(tmp_path, ignore_errors=True)
    data_channel = DataChannel(supported_types=["ts", "state"], eq_fn=lambda a, b: a["state"] == b["state"])
    actions_queue = ActionsQueue(action_names := [chr(x) for x in range(ord("a"), ord("z") + 1)]) # from 'a' to 'z'

    robot = Robot(env, data_channel, actions_queue, actions_fn=lambda env, acts: [env.push(act.name) for act in acts])
    # push 'h' if env._state==[], 'e' if env._state==['h'] and so on until helloworld
    robot.add_controller(lambda data: [Action(TARGET[len(data["state"])])] if len(data["state"]) < len(TARGET) else [])

    robot.run()
    data_channel.close()
    print(f"Final state: '{''.join(env._state)}'") # pylint: disable=protected-access
    assert "".join(env._state) == TARGET # pylint: disable=protected-access

    DataStorer.get_instance().close()

    def replay_controller_fn(data: dict[str, DataItem]) -> list[Action]:
        if len(data["state"]) == len(TARGET):
            return []
        assert data["state"] == data["replay_state"].tolist(), (data["state"], data["replay_state"])
        return [Action(TARGET[len(data["state"])])]

    # just read the data that was created via the data channel
    print("="*80)
    monkeypatch.setenv("ROBOCHAN_STORE_LOGS", "0")
    replay_env = BasicEnv()
    print(f"Start state: '{''.join(replay_env._state)}'") # pylint: disable=protected-access
    replay_data_channel = DataChannel(supported_types=["ts", "state", "replay_ts", "replay_state"],
                                      eq_fn=lambda a, b: a["state"] == b["state"])
    replay_data_producer = ReplayDataProducer(tmp_path / "DataChannel", prefix="replay_")
    replay_actions_queue = ReplayActionsQueue(tmp_path / "ActionsQueue", mode="online", action_names=action_names)
    robot = Robot(replay_env, replay_data_channel, replay_actions_queue,
                  actions_fn=lambda env, acts: [env.push(act.name) for act in acts])
    robot.add_data_producer(replay_data_producer)
    robot.add_controller(replay_controller_fn)

    res = robot.run()
    replay_data_channel.close()
    print(f"Final state: '{''.join(replay_env._state)}'") # pylint: disable=protected-access
    assert "".join(replay_env._state) == TARGET # pylint: disable=protected-access
    assert all(v.exception is None for v in res.values()), res

if __name__ == "__main__":
    test_i_Robot_replay_from_logs_offline_exception(Path(__file__).parent / Path(__file__).stem, pytest.MonkeyPatch())
