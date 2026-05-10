"""types.py - Generic types for robobase"""
from typing import Callable
import numpy as np

DataItem = np.ndarray | int | str | float # used for the DataChannel dictionary: {modality_name: dict[str, DataItem]}
DataEqFn = Callable[[dict[str, DataItem], dict[str, DataItem]], bool] # eq_fn(data1, data2) -> true/false
ControllerFn = Callable[[dict[str, DataItem]], list["Action"]] # takes a data, returns a list of actions (or none for no action) # noqa # pylint: disable=all
ActionsFn = Callable[["Environment", list["Action"]], bool] # takes a generic action and converts it to a env-specific one. Returns a bool (ok/nok) # noqa # pylint: disable=all
