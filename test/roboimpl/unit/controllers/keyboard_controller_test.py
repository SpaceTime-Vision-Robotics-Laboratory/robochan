from robochan import ActionsQueue, DataChannel, Action as Act
from roboimpl.controllers import KeyboardController, Key
import pytest

def test_KeyboardController_keyboard_mock_queue():
    def _keyboard_fn(pressed: set[Key]) -> list[Act]:
        if Key.q in pressed:
            return [Act("act_Q")]
        if Key.x in pressed:
            return [Act("act_X")]
        if Key.Esc in pressed:
            return [Act("act_esc")]
        if len(pressed) > 0:
            raise ValueError
        return []

    aq = ActionsQueue(action_names=["act_Q", "act_X", "act_esc"])
    data_channel = DataChannel(supported_types=["dummy"], eq_fn=lambda a, b: True)
    sd = KeyboardController(data_channel, actions_queue=aq, backend=None, keyboard_fn=_keyboard_fn)

    def make_keypress(key: Key):
        for action in sd.keyboard_fn({key}):
            sd.actions_queue.put(action, data_ts=None, block=True)

    with pytest.raises(ValueError):
        make_keypress(Key.a)
    assert len(aq) == 0
    make_keypress(Key.q)
    assert len(aq) == 1
    make_keypress(Key.x)
    assert len(aq) == 2
    assert aq.get()[0].name == "act_Q"
    assert len(aq) == 1
    make_keypress(Key.Esc)
    assert len(aq) == 2
    with pytest.raises(AttributeError):
        make_keypress(Key.QQ)
    assert len(aq) == 2
    assert aq.get()[0].name == "act_X"
    assert aq.get()[0].name == "act_esc"
    assert len(aq) == 0
