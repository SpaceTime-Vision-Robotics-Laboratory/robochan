import numpy as np
import time
from robochan import DataChannel, DataProducer
from robochan.data_producers2channels import DataProducers2Channels

def test_i_DataProducers2Channels_basic():
    class RGB(DataProducer):
        i = 0
        def produce(self, deps = None):
            time.sleep(0.1)
            RGB.i += 1
            return {"rgb": np.zeros((10, 10)) + RGB.i}

    class RGBReverse(DataProducer):
        def produce(self, deps = None):
            return {"rgb_rev": deps["rgb"][::-1]}

    channel = DataChannel(supported_types=["rgb", "rgb_rev"], eq_fn=lambda a, b: np.allclose(a["rgb"], b["rgb"]))
    data_producers = [RGB(modalities=["rgb"]), RGBReverse(modalities=["rgb_rev"], dependencies=["rgb"])]
    data2channels = DataProducers2Channels(data_producers, [channel])

    assert not channel.has_data()
    # data2channels._data_producer_lists[0].produce_all() # use this if it fails and the thread code is undebuggable.
    data2channels.start()
    time.sleep(1)
    channel.close()

    assert len(channel._data) > 0
    assert (channel._data["rgb"] != 0).all() # unclear where the iteration will stop but we expect at least 2 iterations

if __name__ == "__main__":
    test_i_DataProducers2Channels_basic()
