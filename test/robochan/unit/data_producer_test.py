import pytest
from robochan import LambdaDataProducer, DataItem

def test_LambdaDataProducer_basic():
    def produce_fn(deps: dict[str, DataItem] | None) -> dict[str, DataItem]:
        assert len(deps) == 0, deps
        return {"a": 0}
    dp = LambdaDataProducer(produce_fn, modalities=["a"], dependencies=[])
    assert dp.produce(deps={}) == {"a": 0}

def test_LambdaDataProducer_deps():
    dp = LambdaDataProducer(lambda deps: {"a": 0}, modalities=["a"], dependencies=[])
    dp2 = LambdaDataProducer(lambda deps: {"b": deps["a"] + 1}, modalities=["b"], dependencies=["a"])
    assert dp.produce(deps={}) == {"a": 0}
    with pytest.raises(KeyError):
        dp2.produce(deps={})
    assert dp2.produce(deps=dp.produce(deps={})) == {"b": 1}
