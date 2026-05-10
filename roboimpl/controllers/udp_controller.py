"""udp_controller.py - Converts a UDP message to a generic action. Useful for end-to-end tests."""
from datetime import datetime
import socket
from overrides import overrides

from robochan import DataProducer, BaseController, ActionsQueue, Action
from roboimpl.utils import logger

HOST = "127.0.0.1"
TIMEOUT_S = 10

class UDPController(BaseController):
    """
    Converts a UDP message to a generic action.
    Parameters:
    - data_channel The DataChannel object from which this controller gets data
    - actions_queue The queue of possible actions this controller can send to the data_producer object
    - port The UDP port where this controller listens for commands from
    """
    def __init__(self, data_channel: DataProducer, actions_queue: ActionsQueue, port: int):
        super().__init__(data_channel=data_channel, actions_queue=actions_queue)
        self.port = port

    @overrides
    def run(self):
        self.data_channel_event.wait(TIMEOUT_S)
        (s := socket.socket(socket.AF_INET, socket.SOCK_DGRAM)).bind((HOST, self.port))
        logger.info(f"UDP socket listening to '{HOST}:{self.port}'")

        while self.data_channel.has_data():
            data, addr = s.recvfrom(1024)
            now = datetime.now()
            message = data.decode("utf-8").strip()
            logger.debug(f"Received from '{addr[0]}:{addr[1]}', message: '{message}'")

            try:
                items = message.split(" ")
                action = Action(name=items[0], parameters=tuple(items[1:]))
                self.actions_queue.put(action, data_ts=now, block=True)
                msg = "OK"
            except Exception as e:
                logger.error(msg := str(e))
                msg = f"Unknown message: {message}" if "not in" in msg else msg # for e2e test

            s.sendto(f"{msg}\n".encode("utf-8"), addr)
        s.close()
