"""environment.py - Script defining an interface for environments where a robot exists in"""
from abc import ABC, abstractmethod
import threading
from robochan.utils import parsed_str_type, logger

class Environment(ABC):
    """Generic environment for robots."""
    def __init__(self):
        self.data_ready = threading.Event()

    @abstractmethod
    def get_state(self) -> dict:
        """
        Returns the state of this environment at the some time. A few very important aspects to consider:
        - Ensure that this call is blocking and you manage how it's updated. For example in GymEnvironment we use Events
        - Remember to deepcopy() the returned object or ensure immutability some other way so it's safe 'outside'
        """

    @abstractmethod
    def is_running(self) -> bool:
        """returns true if this environment is running"""

    @abstractmethod
    def get_modalities(self) -> list[str]:
        """The list of raw modalities produced by this environment"""

    def close(self):
        """Closes the environment. It's optional (warn) but useful to have it a method."""
        logger.warning(f"[{parsed_str_type(self)}] Called .close() on this environment but no implementation exists")
