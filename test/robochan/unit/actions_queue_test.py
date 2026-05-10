import pytest
from robochan import ActionsQueue, Action as A

def test_ActionsQueue_ctor():
    with pytest.raises(AssertionError):
         ActionsQueue(action_names=[])

    aq = ActionsQueue(action_names=["a1", "a2"])
    assert aq.action_names == ["a1", "a2"]
    assert len(aq) == 0

def test_ActionsQueue_push_pop():
    aq = ActionsQueue(action_names=["a1", "a2"])
    assert len(aq) == 0
    with pytest.raises(AssertionError): # not an action
        aq.put("a1", data_ts=None)
    aq.put(A("a1"), data_ts=None)
    aq.put(A("a2"), data_ts=None)
    assert len(aq) == 2
    assert aq.get()[0].name == "a1"
    assert len(aq) == 1
    with pytest.raises(AssertionError): # not an action
        aq.put(0, data_ts=None)
    with pytest.raises(AssertionError): # wrong action (not in action_names)
        aq.put(A("a3"), data_ts=None)
    assert aq.get()[0].name == "a2"
    assert len(aq) == 0
