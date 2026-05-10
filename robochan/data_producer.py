"""data_producer.py - interface for DataProducer which are used to produce data to be stored in a DataChannel"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import Callable
from overrides import overrides

from .types import DataItem
from .utils import parsed_str_type
from .environment import Environment

class DataProducer(ABC):
    """DataProducer - interface for a single data producer. It has a produce() method and a list of dependencies"""
    def __init__(self, modalities: list[str], dependencies: list[str] | None = None):
        assert isinstance(modalities, list) and len(modalities) > 0, type(modalities)
        assert dependencies is None or isinstance(dependencies, list), type(dependencies)
        self._dependencies = dependencies or []
        self._modalities = modalities

    @abstractmethod
    def produce(self, deps: dict[str, DataItem] | None = None) -> dict[str, DataItem]:
        """produces the data at the current time given the dependencies, if any"""

    @property
    def modalities(self) -> list[str]:
        """The list of modalities of this data producer"""
        return self._modalities

    @property
    def dependencies(self) -> list[str]:
        """The list of dependencies for this data producer"""
        return self._dependencies

    def __repr__(self):
        return f"[{parsed_str_type(self)}] Modalities: {self.modalities}. Deps: {self.dependencies}"

class LambdaDataProducer(DataProducer):
    """wrapper for a DataProducer with a lambda function so we don't have to inherit it"""
    def __init__(self, produce_fn: Callable[[dict[str, DataItem] | None], dict[str, DataItem]],
                 modalities: list[str], dependencies: list[str] | None = None):
        super().__init__(modalities=modalities, dependencies=dependencies)
        self.produce_fn = produce_fn

    @overrides
    def produce(self, deps: dict[str, DataItem] | None = None) -> dict[str, DataItem]:
        return self.produce_fn(deps)

class RawDataProducer(DataProducer):
    """RawDataProducer simply asks the Environment object for the current state. It's usually the first DP in an app."""
    def __init__(self, env: Environment):
        super().__init__(modalities=env.get_modalities(), dependencies=[])
        self.env = env

    @overrides
    def produce(self, deps: dict[str, DataItem] | None = None) -> dict[str, DataItem]:
        return self.env.get_state()
