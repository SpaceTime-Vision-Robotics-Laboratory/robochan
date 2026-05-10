from robochan.utils.thread_group import ThreadGroup, ThreadStatus
import threading
import pytest
import time

def test_ThreadGroup_ctor():
    with pytest.raises(AssertionError, match="Not all are threads"):
        _ = ThreadGroup({"a": "B"})

    tg = ThreadGroup({"a": threading.Thread(target=lambda: 0)})
    assert len(tg) == 1

def test_ThreadGroup_status():
    tg = ThreadGroup({"a": threading.Thread(target=lambda: 0)})
    assert tg.status() == {"a": ThreadStatus(is_alive=False)}
    assert tg.is_any_dead() is True

def test_ThreadGroup_dict_overrides():
    tg = ThreadGroup({"a": (t := threading.Thread(target=lambda: 0))})
    assert tg.values() == [t]
    assert tg.items() == [("a", t)]

def test_ThreadGroup_start():
    """Check a basic thread doing some work (increment one value)"""
    x = 0
    def f():
        nonlocal x
        x += 1
        while True:
            time.sleep(1)

    tg = ThreadGroup({"a": threading.Thread(target=f, daemon=True)})
    assert x == 0
    tg.start()
    assert tg.status() == {"a": ThreadStatus(is_alive=True)}
    time.sleep(0.001)
    assert x == 1

def test_ThreadGroup_with_exceptions():
    tg = ThreadGroup({
        "a": threading.Thread(target=lambda: 0),
        "b": threading.Thread(target=lambda: (_ for _ in ()).throw(ValueError("errorXYZ"))), # generator can throw :o
    })
    assert tg.status() == {"a": ThreadStatus(is_alive=False), "b": ThreadStatus(is_alive=False)}
    assert tg.is_any_dead() is True
    tg.start()
    res = tg.join(timeout=1)
    assert res["a"] == ThreadStatus(is_alive=False)
    assert res["b"].exception.__str__() == "errorXYZ"
