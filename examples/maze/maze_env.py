"""maze.py -- simple 2D maze environment for testing purposes"""
from __future__ import annotations
import os
from typing import NamedTuple
from datetime import datetime
from loggez import make_logger
import numpy as np
from overrides import overrides

from robochan import Environment
from robochan.utils import wait_and_clear
from robochan.utils import freq_barrier

EMPTY = 0
WALL = 1
PLAYER = 2
EXIT = 3

ENTRY_TO_CHAR = {
    EMPTY: "_",
    WALL: "x",
    PLAYER: "P",
    EXIT: "o",
}
FREQUENCY = int(os.getenv("MAZE_FREQ", "100"))

logger = make_logger("MAZE")

class PointIJ(NamedTuple):
    """2D point tuple in IJ coordinates"""
    i: int
    j: int

    def __add__(self, other: tuple | PointIJ) -> PointIJ:
        return PointIJ(self.i + other[0], self.j + other[1])
    def __sub__(self, other: tuple | PointIJ) -> PointIJ:
        return PointIJ(self.i - other[0], self.j - other[1])
    def __repr__(self):
        return f"({self.i}, {self.j})"

class MazeEnv(Environment):
    """Maze implementation"""
    def __init__(self, maze: np.ndarray, player_pos: PointIJ, exit_pos: PointIJ, max_tries: int):
        super().__init__()
        assert len(maze.shape) == 2, maze.shape
        self.maze_size = tuple(maze.shape)
        self.maze = maze
        self.player_pos = player_pos
        self.exit_pos = exit_pos
        self.max_tries = max_tries

        self.random_seed = None
        self.n_moves = 0
        self.initial_distance = np.linalg.norm(self.exit_pos - self.player_pos, ord=1).item()
        self._prev_time = datetime(1900, 1, 1)
        self.data_ready.set()

    @staticmethod
    def build_random_maze(maze_size: tuple[int, int], walls_prob: float, random_seed: int | None, **kwargs) -> MazeEnv:
        """builds a random maze given a maze size, walls probabilities and an optional seed"""
        random_seed = random_seed or np.random.randint(0, 10000)
        np.random.seed(random_seed)
        logger.info(f"Random seed: {random_seed}")
        maze = (np.random.random(size=maze_size) < walls_prob).astype(int)
        exit_pos, player_pos = np.random.choice(range(np.prod(maze_size)), 2, replace=False).tolist()
        player_pos: PointIJ = PointIJ(player_pos // maze_size[1], player_pos % maze_size[1])
        exit_pos: PointIJ = PointIJ(exit_pos // maze_size[1], exit_pos % maze_size[1])
        maze[*player_pos] = EMPTY # make sure this is empty so we don't have weird behavior
        maze[*exit_pos] = EMPTY # make sure this is empty so we don't have weird behavior
        res = MazeEnv(maze, player_pos, exit_pos, **kwargs)
        res.random_seed = random_seed
        return res

    @overrides
    def is_running(self) -> bool:
        """returns true if the maze is finished"""
        return self.player_pos != self.exit_pos and self.n_moves < self.max_tries

    @overrides
    def get_state(self) -> dict[str, PointIJ | float]:
        """gets the current state of the maze w.r.t the player position. If you call this from outside (i.e. main), also
           do env.data_ready.set() otherwise the env will lock because this is done at env.step() time usually."""
        wait_and_clear(self.data_ready) # wait for green light and set red light
        distance_to_exit = abs(self.exit_pos.i - self.player_pos.i) + abs(self.exit_pos.j - self.player_pos.j)
        return {"distance_to_exit": distance_to_exit, "n_moves": self.n_moves}

    @overrides
    def get_modalities(self) -> list[str]:
        return ["distance_to_exit", "n_moves"]

    @overrides
    def close(self):
        self.data_ready.set() # set to green light

    def is_completed(self) -> bool:
        """returns true if the maze is succesfully completed"""
        return self.player_pos == self.exit_pos

    def _move_player(self, direction: str) -> bool:
        """moves player in one of the 4 directions. Returns true on succes, false otherwise"""
        self._prev_time = freq_barrier(FREQUENCY, self._prev_time)

        self.n_moves += 1
        delta = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
        if direction not in delta.keys():
            logger.debug(f"Direction '{direction}' not in {list(delta.keys())}")
            return False

        new_pos = self.player_pos + delta[direction]
        if new_pos.i < 0 or new_pos.i >= self.maze_size[0] or new_pos.j < 0 or new_pos.j >= self.maze_size[1]:
            logger.debug(f"New position: {new_pos} is outside of {self.maze_size=}")
            return False
        if self.maze[*new_pos] == WALL:
            logger.debug(f"New position: {new_pos} is in a wall.")
            return False
        self.player_pos = new_pos
        if not self.is_running():
            logger.info("Maze environment ending.")
        return True

    def step(self, direction: str) -> bool:
        """step is move_player + data_ready being put to set"""
        assert self.is_running() and self.n_moves < self.max_tries, "maze already finished"
        res = self._move_player(direction)
        self.data_ready.set()
        return res

    def print_maze(self):
        """print the current state of the maze"""
        maze_entries_ix = dict(zip(range(len(ENTRY_TO_CHAR)), ENTRY_TO_CHAR.values()))
        char_maze = np.vectorize(maze_entries_ix.get)(self.maze)
        char_maze[*self.exit_pos] = ENTRY_TO_CHAR[EXIT]
        char_maze[*self.player_pos] = ENTRY_TO_CHAR[PLAYER]
        print(f"Moves: {self.n_moves}")
        for row in char_maze:
            print(" ".join(row))
        print("=" * 80)
