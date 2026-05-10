"""sync.py - synchronization primitives"""
import threading
from datetime import datetime
import time

def wait_and_clear(event: threading.Event, timeout: float | None = None):
    """wait for green light and set red light again. Used in get_state() at the beginning."""
    event.wait(timeout)
    event.clear()

def freq_barrier(frequency: float, prev_time: datetime) -> datetime:
    """sleeps for the amount of time required between two consuecitive runs as per frequency. Returns new time."""
    assert frequency > 0, frequency
    diff = (1 / frequency) - ((now := datetime.now()) - prev_time).total_seconds()
    time.sleep(diff if diff > 0 else 0)
    return now
