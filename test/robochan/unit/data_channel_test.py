import pytest
from robochan.data_channel import DataChannel

def test_DataChannel_ctor():
    with pytest.raises(AssertionError):
        _ = DataChannel(supported_types=[], eq_fn=lambda a, b: a==b)

    channel = DataChannel(supported_types=["rgb"], eq_fn=lambda a, b: a==b)
    assert channel.supported_types == {"rgb"}

def test_DataChannel_put():
    channel = DataChannel(supported_types=["rgb", "hsv"], eq_fn=lambda a, b: a==b)
    with pytest.raises(AssertionError):
        channel.put({"rgb": 0})
    with pytest.raises(AssertionError):
        channel.put({"rgb": 0, "hsv": 0, "asdf": 0})
    assert not channel.has_data()
    channel.put({"rgb": 0, "hsv": 0})
    assert channel.has_data()

def test_DataChannel_eq_fn():
    channel = DataChannel(supported_types=["rgb"], eq_fn=lambda a, b: a==b)
    d1 = {"rgb": 1}
    d2 = {"rgb": 2}
    d3 = {"rgb": 1}
    assert not channel.eq_fn(d1, d2)
    assert channel.eq_fn(d1, d3)

def test_DataChannel_subscribe():
    channel = DataChannel(supported_types=["item"], eq_fn=lambda a, b: a==b)
    event = channel.subscribe()

    assert not event.is_set()

    channel.put({"item": 0}) # put new item -> event is set
    assert event.is_set()
    event.clear()

    assert not event.is_set()
    channel.put({"item": 0}) # put same item, the event is not set again
    assert not event.is_set()

    channel.put({"item": 1}) # put other item -> event is set
    assert event.is_set()
