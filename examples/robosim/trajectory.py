#!/usr/bin/env python3
"""A simple TCP client to connect to the simulator server and interact with the robot/UAV"""
# pylint: disable=duplicate-code, import-error, wrong-import-order
import time
from datetime import datetime
import numpy as np
from numpy.typing import NDArray as ND
from spatialmath.base import isR, vexa, trlog, tr2rpy
from loggez import make_logger

from robochan import DataChannel, ActionsQueue
from robochan.utils import freq_barrier
from robochan.controller import BaseController
from roboimpl.controllers import DisplayerBackend, Key

from robosim_env import RobosimEnv

Point3D = ND["3,"]
Point6D = ND["6,"]
Pose4x4 = ND["4,4"]
Rot3x3 = ND["3,3"]

logger = make_logger("CLIENT", exists_ok=True)
np.set_printoptions(precision=3, linewidth=120)
FREQ = 10

# utils

def fmt(arr: np.ndarray, precision: int=2) -> str:
    """formats a numpy array for logging as tuple"""
    return "(" + ", ".join(f"{float(x):.{precision}g}" for x in arr) + ")"

def _get_maxes(state: dict) -> Point6D:
    try:
        uav_type = state["robot"]["type"]
    except Exception as e:
        logger.error(state)
        raise e

    if uav_type == "UAVLevel1":
        maxes = np.array(state["robot"]["max_velocities"], "float32")
    elif uav_type == "UAVLevel2":
        maxes = np.array(state["robot"]["max_accelerations"], "float32")
    else:
        raise ValueError(uav_type)
    return maxes

# math

def renormalize_rotation_matrix(rot: Rot3x3, tol: float=1e10) -> Rot3x3:
    """uses SVD to renormalize a rotation matrix if it drifted too much (i.e. during trajectory updates)"""
    if isR(rot, tol=tol):
        return rot
    logger.debug(f"Renormalizing R as err is {np.linalg.norm((rot @ rot.T) - np.eye(3)):.7f}")
    U, _, Vt = np.linalg.svd(rot)
    D = np.diag([1, 1, np.linalg.det(U @ Vt)]) # force det=1 (not -1)
    new_rot = U @ D @ Vt
    assert isR(new_rot, tol=1e10), new_rot
    return new_rot

def relative_velocity_from_poses(pose1: Pose4x4, pose2: Pose4x4) -> Point6D:
    """returns a relative velocity (v, w) from two poses. Used to (linearly) compute trajectories. Aka twist"""
    T_rel = np.linalg.inv(pose1) @ pose2 # compute relative pose (in body frame!!)
    T_rel[0:3, 0:3] = renormalize_rotation_matrix(T_rel[0:3, 0:3], tol=1e10)
    velocity_rel = vexa(trlog(T_rel, tol=1e10)) # relative velocity for linear interpolation (tangent space)
    return velocity_rel

def pose_to_trans_euler(pose: Pose4x4) -> np.ndarray:
    """converts a pose to a 6DoF translation + euler vector, mostly for printing reasons (4, 4) -> (6, )"""
    return np.array([*pose[0:3, 3], *tr2rpy(pose)], dtype="float32")

# controllers logic

def create_traj_level1(current_pose: Pose4x4, via_points: list[Pose4x4], max_velocities: Point6D) -> list[Point6D]:
    """creates a trajectory for a velocity-based "level1" uav (kinematic)"""
    l, r  = [current_pose, *via_points[0:-1]], via_points # start from the current pos. of the UAV
    traj = [] # 1D all the trajectory points through all via points
    for t1, t2 in zip(l, r):
        velocity_rel = relative_velocity_from_poses(t1, t2)
        abs_rel = np.abs(velocity_rel)
        steps = (abs_rel // max_velocities + (abs_rel % max_velocities == 0)).astype(int).max() + 1
        traj.extend(np.array([velocity_rel / steps] * steps, dtype="float32"))
    logger.info(f"trajectory has {len(traj)} steps across {len(via_points)} via points")
    logger.info(f"current position: {fmt(pose_to_trans_euler(current_pose))}")
    logger.info(f"target position: {fmt(pose_to_trans_euler(via_points[-1]))}")
    return traj

def create_traj_level2(current_pose: Pose4x4, via_points: list[Pose4x4], max_accelerations: Point6D,
                       dt: float, drag_coefficient: float) -> list[Point6D]:
    """creates a trajectory for a acceleration-based "level2" uav (simple physics)"""
    # level 2 physics: v[t+1] = v[t] + dt * (a[t] - k * v[t]) => v[t+1] - v[t] = dt * (a[t] - k * v[t])
    # = dt*a[t] - dt * k * v[t] => a[t] = (v[t+1] - v[t]) / dt +  k * v[t]

    def compute_d_brk(v: float, a_max: float, k: float, dt: float) -> tuple[float, list[float]]:
        # 0 acceleration -> we just lose speed via the drag
        assert v > 0, v
        d = 0
        vs = []
        while v > 0:
            d = d + v * dt
            v = v + (-a_max - k * v) * dt
            vs.append(v)
        return d, vs

    def triangle_velocities(d_relative: float, a_max: float, k: float, dt: float) -> list[float]:
        # just for linear and just for 1 axis, a_max and k (drag) are given
        assert isinstance(d_relative, float), (d_relative, type(d_relative))
        assert isinstance(a_max, float), (a_max, type(a_max))
        d_fwd = d_brk = v_fwd = 0

        vs, vs_back = [], []
        while d_fwd + d_brk < d_relative:
            d_fwd = d_fwd + v_fwd * dt
            v_fwd = v_fwd + (a_max - k * v_fwd) * dt

            d_brk, vs_back = compute_d_brk(v_fwd, a_max, k, dt)
            vs.append(v_fwd)
        vs.extend(vs_back)
        return vs

    def triangle_accelerations_v1(t1: Pose4x4, t2: Pose4x4, a_max: Point6D, k: float, dt: float) -> list[float]:
        """v1: each ax is computed independently as a 1D component of the 6DoF twist"""
        accels = []
        twist = relative_velocity_from_poses(t1, t2) # (6, )
        for i in range(len(twist)): # each ax one by one, linear and rotation
            # velocities of each particular ax, linear or rotation
            velocities = triangle_velocities(abs(twist[i].item()), a_max[i].item(), k, dt)
            accel_one_ax = []
            # v[t+1] = v[t] + (a[t] - k * v[t]) * dt => a[t] = (v[t+1] - v[t]) / dt + k * v[t]
            for vt, vt1 in zip(velocities[0:-1], velocities[1:]):
                accel_one_ax.append( (vt1 - vt) / dt + k * vt)
            accels.append(accel_one_ax)

        # put them in a single array padded with zeros
        max_dim = max(len(x) for x in accels)
        res = np.zeros((max_dim, len(twist)), dtype="float32") # (N, 6) padded with 0s
        for i, accel_one_ax in enumerate(accels):
            res[0:len(accel_one_ax), i] = accel_one_ax
        res = res * np.sign(twist)[None] # sign here and abs() in triangle_velocities(). (N, 6) * (1, 6)
        # res[:, 3:6] = 0 # DEBUG: set rotations to 0
        return res

    res = []
    for l, r in zip([current_pose, *via_points[0:-1]], via_points): # 2 by 2 points
        res.extend(triangle_accelerations_v1(l, r, max_accelerations, drag_coefficient, dt))
    return res

class TrajectoryController(BaseController):
    """Trajectory controller: interface between the controller and robosim"""
    def __init__(self, data_channel: DataChannel, actions_queue: ActionsQueue,
                 env: RobosimEnv, displayer_backend: DisplayerBackend):
        super().__init__(data_channel, actions_queue)
        self.env = env
        self.backend = displayer_backend

    def run(self):
        """the controller managing the trajectories (mission)"""
        recv = self.env.send_recv_packet({"cmd": "sim_get_info"})
        assert "control_loop_rate_hz" in recv, recv
        mission_started = False
        prev = datetime.now()
        while True:
            prev = freq_barrier(FREQ, prev)
            pressed = self.backend.get_pressed_keys()
            if mission_started: # cannot do anything while mission is running
                if len(pressed) != 0:
                    logger.error("Cannot do any actions while mission is running")
                time.sleep(0.1)
                msg = self.env.send_recv_packet({"cmd": "mission_get_state"})
                if msg["mission_state"] != "running":
                    logger.info(f"Mission ended: {msg}")
                    mission_started = False
                continue

            if Key.y in pressed:
                self.env.send_recv_packet({"cmd": "mission_add_via_point"})

            if Key.i in pressed:
                self.env.send_recv_packet({"cmd": "mission_clear_via_points"})

            if Key.u in pressed:
                state = self.env.send_recv_packet({"cmd": "robot_get_state", "robot_id": self.env.robot_id})
                msg = self.env.send_recv_packet({"cmd": "mission_get_state"})
                if "error" in msg or "via_points" in msg and len(via_points := msg["via_points"]) == 0:
                    logger.error(msg)
                    continue
                if msg["mission_state"] == "running":
                    logger.error(f"mission is already running: {msg}")
                    continue

                maxes = _get_maxes(state) # get once per mission
                traj = None
                if state["robot"]["type"] == "UAVLevel1":
                    traj = create_traj_level1(np.array(state["robot"]["pose"]), np.array(via_points), maxes)
                elif state["robot"]["type"] == "UAVLevel2":
                    drag_coefficient = state["robot"]["drag_coefficient"]
                    dt = 1 / self.env.send_recv_packet({"cmd": "sim_get_info"})["control_loop_rate_hz"]
                    traj = create_traj_level2(np.array(state["robot"]["pose"]), np.array(via_points),
                                            maxes, dt, drag_coefficient)

                if traj is not None:
                    res = self.env.send_recv_packet({"cmd": "mission_start", "trajectory": [x.tolist() for x in traj]})
                    logger.info(f"Starting mission for uav: {state['robot']['type']}: {res}")
                    if "error" in res:
                        logger.error(res)
                    else:
                        mission_started = True
                else:
                    logger.error(f"No trajectory was created. UAV type: {state['robot']['type']}")

            pressed.clear()
