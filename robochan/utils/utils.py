"""generic utils file"""
from pathlib import Path
import os
from datetime import datetime
from typing import Any
import numpy as np
from loggez import make_logger

def get_project_root() -> Path:
    """returns the project root"""
    return Path(__file__).parents[2]

# Create a logger. For the logs dir we have a few options: ROBOCHAN_STORE_LOGS must be >=1 otherwise no logs.
# For the file, if the env. var ROBOCHAN_LOGS_DIR is set, then it's used, otherwise defaults to proj_root/logs/now_iso
logs_dir = os.getenv("ROBOCHAN_LOGS_DIR", get_project_root() / "logs" / datetime.now().strftime("%Y-%m-%dT%H-%M-%S"))
log_file = f"{logs_dir}/ROBOCHAN.txt" if os.getenv("ROBOCHAN_STORE_LOGS", "1") in ("1", "2") else None
logger = make_logger("ROBOCHAN", log_file=log_file)

def parsed_str_type(item: Any) -> str:
    """Given an object with a type of the format: <class 'A.B.C.D'>, parse it and return 'A.B.C.D'"""
    return str(type(item)).rsplit(".", maxsplit=1)[-1][0:-2]

def load_npz_as_dict(path: Path) -> dict[str, Any]:
    """Loads a stored npz as a dict by trying our best to unpickle it"""
    data = np.load(path, allow_pickle=True)
    if "arr_0" in data.keys() and len(data.keys()) == 1: # compat mode
        return data["arr_0"].item()
    res = {}
    for k, v in data.items():
        res[k] = v if v.shape == (0, ) or (len(v.shape) > 0 and v.shape[0] > 0 and isinstance(v[0], str)) else v.item()
    return res
