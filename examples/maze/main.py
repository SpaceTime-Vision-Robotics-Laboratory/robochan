#!/usr/bin/env python3
"""maze main function"""
from __future__ import annotations
import sys
import os
from dataclasses import dataclass
from pathlib import Path
from argparse import ArgumentParser, Namespace
import random
from loggez import make_logger

from robochan import Robot, DataChannel, ActionsQueue, DataItem, Action

sys.path.append(Path(__file__).parent.__str__())
from examples.maze.maze_env import MazeEnv, PointIJ # pylint: disable=all

logger = make_logger("MAZE_SOLVER")

MAZE_SIZE = (10, 10)
MAZE_WALLS_PROB = 0.2
MAZE_MAX_TRIES = 200
INF = 2**31
PRINT = os.getenv("MAZE_PRINT", "0") == "1"

def random_controller_fn(data: dict[str, DataItem]) -> list[Action]: # pylint:disable=unused-argument
    """random planner"""
    res = random.choice(["up", "down", "left", "right"])
    logger.debug(f"Doing action: {res}")
    return [Action(res)]

@dataclass
class State:
    position: PointIJ # current position
    distance: float # distance from now to goal
    move: str | None # what move I took here
    prev_state: State | None # the previous state

class Strategy1:
    def __init__(self):
        self.pos_to_distance: dict[PointIJ, float] = {} # {relative position: score}, -inf if wall or empty path
        self.state = State(position=PointIJ(0, 0), distance=2**31, move=None, prev_state=None)

    def move(self, move: str) -> list[Action]:
        """wrapper to update stuff before returning"""
        self.state.move = move
        move_to_delta = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
        logger.debug(f"Move: {move}. Position: {self.state.position}. Distance: {self.state.distance}.")
        if self.pos_to_distance.get(self.state.position + move_to_delta[self.state.move], 0) == INF:
            logger.debug(self.pos_to_distance)
            raise ValueError("stuck most likely")
        return [Action(move)]

    def __call__(self, data: dict[str, DataItem]) -> list[Action]:
        move_to_rev = {"up": "down", "right": "left", "down": "up", "left": "right"}
        move_to_delta = {"up": (-1, 0), "down": (1, 0), "left": (0, -1), "right": (0, 1)}
        moves = list(move_to_rev)
        curr_distance = data["distance_to_exit"]
        prev_state = self.state

        if len(self.pos_to_distance) == 0: # note: it's safe to do it here as you cannot spawn in a wall.
            self.pos_to_distance[self.state.position] = self.state.distance = data["distance_to_exit"]
            logger.debug("> First move")
            return self.move("up")

        self.state = State(
            position=prev_state.position + move_to_delta[prev_state.move],
            distance=curr_distance,
            move=None,
            prev_state=prev_state
        )

        if curr_distance == prev_state.distance: # last move was into a wall, so we mark it as bad and get rid of it
            # mark that position as inf and revert to previous one
            self.pos_to_distance[self.state.position] = INF
            self.state = prev_state
            logger.debug("> Hit wall, reverting state")

        # pick first unexplored move
        self.pos_to_distance[self.state.position] = curr_distance
        n_walls = 0
        potential_moves, potential_scores = [], []
        for potential_move in moves:
            potential_position = self.state.position + move_to_delta[potential_move]
            if potential_position not in self.pos_to_distance:
                logger.debug("> Go in first unexplored move")
                return self.move(potential_move)
            else: # was previously explored
                potential_moves.append(potential_move)
                potential_scores.append(self.pos_to_distance[potential_position])
                if self.pos_to_distance[potential_position] == INF:
                    n_walls += 1

        assert n_walls < 4, "stuck?"
        if n_walls == 3:
            self.pos_to_distance[self.state.position] = INF
            logger.debug("> 3 walls, going back")
        logger.debug(f"> {n_walls} walls. Picking smallest distance path. If >1, pick at random")
        min_score = min(potential_scores)
        potential_moves = [move for i, move in enumerate(potential_moves) if potential_scores[i] == min_score]
        return self.move(random.choice(potential_moves))

def actions_fn(maze: MazeEnv, actions: list[Action]):
    for action in actions:
        maze.step(action.name)
        if PRINT:
            print("\n" * 20)
            maze.print_maze()

def get_args() -> Namespace:
    """cli args"""
    parser = ArgumentParser()
    parser.add_argument("strategy")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--results_path", type=Path, default=Path.cwd() / "results.csv")
    args = parser.parse_args()
    return args

def main(args: Namespace):
    """main fn"""
    controller_fn = {
        "random": random_controller_fn,
        "strategy1": Strategy1(),
    }[args.strategy]
    maze = MazeEnv.build_random_maze(maze_size=MAZE_SIZE, walls_prob=MAZE_WALLS_PROB,
                                     random_seed=args.seed, max_tries=MAZE_MAX_TRIES)
    logger.info(f"Maze started. initial distance of: {maze.initial_distance}")
    maze.print_maze()

    actions_queue = ActionsQueue(action_names=["up", "down", "left", "right"])
    data_channel = DataChannel(supported_types=["distance_to_exit", "n_moves"],
                               eq_fn=lambda a, b: a["n_moves"] == b["n_moves"])

    robot = Robot(env=maze, data_channel=data_channel, actions_queue=actions_queue, actions_fn=actions_fn)
    robot.add_controller(controller_fn, name="Maze Planner")
    robot.run()
    data_channel.close()

    maze.print_maze()
    logger.info(f"Maze {'finished in' if maze.is_completed() else 'not finished after'} {maze.n_moves} moves.")
    open(args.results_path, "a").write(f"{maze.random_seed},{args.strategy},{maze.n_moves}\n")

if __name__ == "__main__":
    main(get_args())
