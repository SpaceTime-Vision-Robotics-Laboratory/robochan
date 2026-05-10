"""data_producers2channels.py implements the mapping between a list of producers and a list of channels"""
import threading
import time
import traceback

from .utils import ThreadGroup, logger
from .types import DataItem
from .data_producer import DataProducer
from .data_channel import DataChannel, DataChannelClosedError

def _topo_sort_producers(producers: list[DataProducer]) -> list[DataProducer]:
    """does a topological sort of the data producers given their dependencies and their modalities"""
    consumers: dict[str, list[int]] = {} # Map dependency string -> list of consumer indices
    degrees: list[int] = [len(p.dependencies) for p in producers]

    for i, p in enumerate(producers):
        for dep in p.dependencies:
            consumers.setdefault(dep, []).append(i)

    queue: list[int] = [i for i, d in enumerate(degrees) if d == 0]
    res: list[DataProducer] = []

    while len(queue) > 0:
        curr_idx = queue.pop()
        res.append(producers[curr_idx])
        for mod in producers[curr_idx].modalities:
            for c_idx in consumers.get(mod, []):
                degrees[c_idx] -= 1
                if degrees[c_idx] == 0:
                    queue.append(c_idx)

    if len(res) != len(producers):
        raise ValueError("couldn't solve")
    return res

class _DataProducerList:
    """
    _DataProducerList implements a 1 channel : M producers (assumed topo-sorted) graph where all M write to it.
    Note: this class can be used to debug programs as produce_all can be ran without any threading, if i.e. one data
    producer is misbehaving, like crashing mid (multi-threaded) execution for some data.
    """
    def __init__(self, data_channel: DataChannel, data_producers: list[DataProducer]):
        assert isinstance(data_channel, DataChannel), f"data_channel is of wrong type: {type(data_channel)}"
        assert (A := data_channel.supported_types) == set(B := sum([d.modalities for d in data_producers], [])), \
            f"Data Channel types: {[*A]} vs. Data Producers modalities: {B}\nMissing: {[*A - {*B}]}"
        assert len(B) == len(set(B)), f"One or more DataProducers provide the same modality! {B}"
        self.data_channel = data_channel
        self.data_producers = data_producers

    def produce_all(self) -> dict[str, DataItem]:
        """Calls all the producers in topological order and synchronous"""
        data: dict[str, DataItem] = {}
        for data_producer in self.data_producers:
            producer_data = data_producer.produce(deps=data)
            assert isinstance(producer_data, dict), f"Producer '{data_producer}' didn't produce a dict: {producer_data}"
            if (A := set(producer_data.keys())) != set(B := data_producer.modalities):
                raise KeyError(f"Producer '{data_producer}' with modalities {B} produced {A}.")
            data |= producer_data
        return data

class DataProducers2Channels(threading.Thread):
    """
    DataProducers2Channels is a generalization of DataProducerList from 1 channel : M producers to N : M.
    The end-goal is to have a async-based where we actually have one thread per DataProducer. Right now this is just
    a generalization of the (sync) DataProducerList, so each underlying may do the same work multiple times.
    """
    def __init__(self, data_producers: list[DataProducer], data_channels: list[DataChannel]):
        assert isinstance(dps := data_producers, list) and all(isinstance(dp, DataProducer) for dp in dps), dps
        assert isinstance(dcs := data_channels, list) and all(isinstance(dc, DataChannel) for dc in dcs), dcs
        super().__init__(daemon=True)
        self.data_channels = data_channels
        self.data_producers = _topo_sort_producers(data_producers)
        self._data_producer_lists: list[_DataProducerList] = [] # mostlfy for debugging, see test_i_DataProducers2DCs

        self.workers = ThreadGroup()
        for i, data_channel in enumerate(data_channels):
            channel_dps = []
            for dp in self.data_producers:
                if any(dp_mod in data_channel.supported_types for dp_mod in dp.modalities):
                    channel_dps.append(dp)
            self._data_producer_lists.append(_DataProducerList(data_channel=data_channel, data_producers=channel_dps))
            self.workers[f"DPList-{i}"] = threading.Thread(target=self._worker_fn, daemon=True, name=f"DPList-{i}",
                                                           args=(self._data_producer_lists[-1], ))

    def run(self):
        self.workers.start()
        while not self.workers.is_any_dead():
            time.sleep(1)

    def _worker_fn(self, dp_list: _DataProducerList):
        # This function operates at one DataChannel and the DataProducers of this singular channel. We have 1 thread for
        # each DataChannel and its list.
        while True:
            try:
                data = dp_list.produce_all()
                dp_list.data_channel.put(data)
            except DataChannelClosedError: # in case it closes between is_open() check and put(data)
                break
            except Exception as e:
                logger.error(f"Error {e}\nTraceback: {traceback.format_exc()}")
                break
