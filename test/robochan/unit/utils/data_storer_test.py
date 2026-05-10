from pathlib import Path
from datetime import datetime
from queue import Empty
from robochan.utils import DataStorer
import numpy as np
import pytest

def test_DataStorer_constructor_creates_directory(tmp_path: Path):
    target = tmp_path / "store_dir"
    assert not target.exists()

    DataStorer(target)
    assert target.exists()
    assert target.is_dir()

def test_push_and_get_and_store_flow(tmp_path):
    ds = DataStorer(tmp_path)
    t1, t2 = datetime.now(), datetime.now()
    arr1, arr2 = np.array([1, 2, 3]), np.array([4, 5, 6])

    # Calling before push should raise
    with pytest.raises(Empty):
        ds.get_and_store()
    with pytest.raises(AssertionError, match="Can only push dicts to DataStorer"):
        ds.push(arr1, "test", t1)

    ds.push({"my_key": arr1}, "test", t1)
    ds.push({"my_key2": arr2}, "test", t2)
    assert ds.data_queue.qsize() == 2

    # store and check twice
    ds.get_and_store()
    assert ds.data_queue.qsize() == 1
    ds.get_and_store()
    assert ds.data_queue.qsize() == 0
    with pytest.raises(Empty):
        ds.get_and_store()

    # verify data on disk
    files = sorted(list((tmp_path / "test").iterdir()), key=lambda p: p.name) # sort for consistency
    assert len(files) == 2
    saved_arrays = [np.load(f, allow_pickle=True) for f in files]
    assert np.array_equal(saved_arrays[0]["my_key"], arr1)
    assert np.array_equal(saved_arrays[1]["my_key2"], arr2)
