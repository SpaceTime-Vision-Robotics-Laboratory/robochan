#!/usr/bin/env python3
"""replay.py - Example on how to use the replay functionalities (ReplayDataProducer, ActionsQueue [TODO]) of robobase"""
# TODO: make a readme or something.
import sys
from robochan import Robot, DataChannel, ActionsQueue
from robochan.replay import ReplayDataProducer
from robochan.utils import logger

from main import ( # pylint: disable=all
    MAZE_MAX_TRIES, MAZE_WALLS_PROB, MAZE_SIZE, MazeEnv, Strategy1, actions_fn, random_controller_fn)

def main():
    """main fn"""
    controller_fn = {
        "random": random_controller_fn,
        "strategy1": Strategy1(),
    }["strategy1"]
    maze = MazeEnv.build_random_maze(maze_size=MAZE_SIZE, walls_prob=MAZE_WALLS_PROB,
                                     random_seed=42, max_tries=MAZE_MAX_TRIES)
    logger.info(f"Maze started. initial distance of: {maze.initial_distance}")
    maze.print_maze()

    actions_queue = ActionsQueue(action_names=["up", "down", "left", "right"])
    supported_types = ["distance_to_exit", "n_moves"]
    supported_types = [*supported_types, *[f"replay_{s}" for s in supported_types]]
    data_channel = DataChannel(supported_types=supported_types, eq_fn=lambda a, b: a["n_moves"] == b["n_moves"])

    robot = Robot(env=maze, data_channel=data_channel, actions_queue=actions_queue, actions_fn=actions_fn)
    robot.add_data_producer(ReplayDataProducer(sys.argv[1], prefix="replay_"))
    robot.add_controller(controller_fn, name="Maze Planner")
    robot.run()
    data_channel.close()

    maze.print_maze()
    logger.info(f"Maze {'finished in' if maze.is_completed() else 'not finished after'} {maze.n_moves} moves.")

if __name__ == "__main__":
    main()
