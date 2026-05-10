"""action.py The generic action class"""
from __future__ import annotations
from dataclasses import dataclass
from typing import Any

@dataclass(frozen=True)
class Action:
    """action class is a name (str) + parameters (any)"""
    name: str
    parameters: tuple[Any, ...] = ()

    def __post_init__(self):
        assert isinstance(self.name, str), type(self.name)
        assert isinstance(self.parameters, tuple), type(self.parameters)

    def __repr__(self):
        return f"Action({self.name}{'' if self.parameters == tuple() else f' {self.parameters}'})"

    def __eq__(self, other: Action) -> bool:
        assert isinstance(other, Action), type(other)
        return self.name == other.name and self.parameters == other.parameters
