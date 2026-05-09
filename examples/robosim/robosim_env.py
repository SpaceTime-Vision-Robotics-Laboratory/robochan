"""wrapper for thread-safe client->server conn"""
# pylint: disable=duplicate-code, import-error
from __future__ import annotations
import os
import socket
import zlib
import threading
from datetime import datetime
import numpy as np
import msgpack
from overrides import overrides
from loggez import make_logger

from robobase import Environment # pylint: disable=import-error
from robobase.utils import freq_barrier, wait_and_clear # pylint: disable=import-error

SOCKET_TIMEOUT_S = int(os.getenv("SOCKET_TIMEOUT_S", "1000")) # big number so we can breakpoint w/o timeouts.
FREQ = 60
WAIT_FOR_DATA_SECONDS = 5

logger = make_logger("ROBOSIM_ENV")

def send_packet(sock: socket.socket, data: dict, close_connection: bool=False, add_timestmap: bool=True):
    """pack the message in messagepack format + length-prefixed for TCP stream then send it through the socket"""
    assert isinstance(data, dict), (data, type(data))
    if add_timestmap:
        assert "timestamp" not in data.keys(), data
        data["timestamp"] = datetime.now().isoformat()
    packed_data = msgpack.packb(data)
    packet = len(packed_data).to_bytes(4, "big") + packed_data # <SIZE-4b><packed_data>
    logger.trace(f"Sending {len(packet)} bytes through the wire")
    sock.sendall(packet)

    if close_connection:
        sock.close()

def recv_packet(sock: socket.socket) -> dict:
    """reads a packet from the server. First 4 bytes for len, then the rest of the message"""
    def _recvall(sock: socket.socket, n: int) -> bytes:
        """recvall receives all n bytes at once from a tcp socket"""
        buf = bytearray()
        while len(buf) < n:
            if not (chunk := sock.recv(n - len(buf))):
                raise ConnectionError
            buf.extend(chunk)
        return bytes(buf)

    packet_len = int.from_bytes(_recvall(sock, 4), "big")
    packet: dict = msgpack.unpackb(_recvall(sock, packet_len), raw=False)
    assert isinstance(packet, dict), f"packet is not dictionary: {type(packet)}"
    return packet

class RobosimEnv(Environment):
    """wrapper for thread-safe client->server conn"""
    def __init__(self, host: str, port: int):
        super().__init__()
        self.host = host
        self.port = port

        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock_lock = threading.Lock()

        self.robot_id = self._init_connection_to_robot()
        self._state_lock = threading.Lock()
        self._state = None

        threading.Thread(target=self._stream_worker, daemon=True).start()

    @overrides
    def is_running(self) -> bool: # noqa # pylint: disable=missing-function-docstring
        try:
            self.sock.getpeername()
            return True
        except Exception as e:
            logger.error(e)
            return False

    @overrides
    def get_modalities(self) -> list[str]: # noqa # pylint: disable=missing-function-docstring
        return ["timestamp", "robot", "rgb", "fpv_frame_id", "fpv_compressed", "fpv_shape"]

    @overrides
    def close(self): # noqa # pylint: disable=missing-function-docstring
        self.data_ready.set()
        self.sock.close()

    @overrides
    def get_state(self) -> dict: # noqa # pylint: disable=missing-function-docstring
        wait_and_clear(self.data_ready, WAIT_FOR_DATA_SECONDS if self._state is None else None)
        with self._state_lock:
            res = self._state
            if "rgb" not in res:
                frame_bytes = zlib.decompress(res["fpv_compressed"])
                proc = len(res["fpv_compressed"]) / np.prod(res["fpv_shape"]) * 100
                logger.log_every_s(f"Recv: {len(res['fpv_compressed'])} -> "
                                   f"{np.prod(res['fpv_shape'])} bytes ({proc:.2f}%)", "TRACE")
                res["rgb"] = np.frombuffer(frame_bytes, dtype=np.uint8).reshape(res["fpv_shape"])
            return res

    def send_recv_packet(self, data: dict) -> dict:
        """send a packet and returns an answer"""
        with self.sock_lock:
            if data["cmd"] != "robot_get_state_with_camera":
                logger.debug(f"Sending: {data}")
            send_packet(self.sock, data, add_timestmap=False)
            res = recv_packet(self.sock)
            if "fpv_compressed" not in res:
                logger.debug(f"Received: {res}")
            if "error" in res:
                logger.error(res)
            return res

    def send_recv_packets(self, data: list[dict]) -> list[dict]:
        """sends many packets and returns the answers"""
        if len(data) == 0:
            return []
        res = []
        logger.log_every_s(f"Sending {len(data)} messages", "DEBUG", log_to_next_level=True)
        with self.sock_lock:
            for msg in data:
                send_packet(self.sock, msg, add_timestmap=False)
            for _ in range(len(data)):
                res.append(recv_packet(self.sock))
        return res

    def get_maxes(self) -> np.ndarray:
        """return the max allowed by this uav"""
        state = self.send_recv_packet({"cmd": "robot_get_state", "robot_id": self.robot_id})
        uav_type = state["robot"]["type"]

        if uav_type == "UAVLevel1":
            maxes = np.array(state["robot"]["max_velocities"], "float32")
        elif uav_type == "UAVLevel2":
            maxes = np.array(state["robot"]["max_accelerations"], "float32")
        else:
            raise ValueError(uav_type)
        return maxes

    def _init_connection_to_robot(self) -> int:
        self.sock.connect((self.host, self.port))
        self.sock.settimeout(SOCKET_TIMEOUT_S)
        msg = {"cmd": "connect"}
        recv = self.send_recv_packet(msg)
        assert "status" in recv and recv["status"] == "connected", recv
        logger.info(f"Connected to '{self.host}:{self.port}' (robot id: {recv['id']})")
        return recv["id"]

    def _stream_worker(self):
        stream_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        stream_sock.connect((self.host, self.port))
        stream_sock.settimeout(SOCKET_TIMEOUT_S)

        prev = datetime.now()
        while self.is_running():
            prev = freq_barrier(FREQ, prev)

            data = {"cmd": "robot_get_state_with_camera", "robot_id": self.robot_id}
            send_packet(stream_sock, data, add_timestmap=False)
            res = recv_packet(stream_sock)

            if "error" in res:
                logger.error(res)

            with self._state_lock:
                self._state = res
                self.data_ready.set()
