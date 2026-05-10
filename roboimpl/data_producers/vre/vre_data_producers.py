"""vre_data_producers.py - Interface between video-representations-extractor and robobase"""
from pathlib import Path
from vre.representations import build_representations_from_cfg # pylint: disable=all
from vre import MemoryData, Representation, ReprOut # pylint: disable=all
from vre.representations.mixins import LearnedRepresentationMixin # pylint: disable=all
from vre_repository import get_vre_repository # pylint: disable=all

from robochan import DataProducer, DataItem
from roboimpl.utils import logger

class VREDataProducer(DataProducer):
    """Interface between video-representations-extractor and robobase"""
    def __init__(self, representation: Representation | LearnedRepresentationMixin):
        self.repr = representation
        super().__init__(modalities=[self.repr.name], dependencies=self.repr.dep_names)

    def produce(self, deps: dict[str, DataItem] | None = None) -> dict[str, DataItem]:
        if isinstance(self.repr, LearnedRepresentationMixin) and not self.repr.setup_called:
            logger.debug(f"Repr: {self.repr.name}. Device: {self.repr.device}. You can control via VRE_DEVICE=cpu/cuda")
            self.repr.vre_setup()
        # TODO: we may need to be able to pass a compute_fn to change defaults (i.e. resize or not) from app level.
        # Note that while VRE operates at batch level, robobase operates at frame level (streaming), so we create a
        # batch of size 1: (B, H, C) -> (1, B, H, C) -> vre -> (1, B, H, C') -> (B, H, C').
        video = deps["rgb"][None] # rgb must always be here in thge case of VRE. (1, B, H, 3)
        dep_data = []
        for dep_name in self.repr.dep_names:
            dep_data.append(ReprOut(frames=video, output=MemoryData(deps[dep_name][None]), key=[0]))
        out_repr = self.repr.compute(video=video, ixs=[0], dep_data=dep_data)
        return {self.repr.name: out_repr.output[0]}

def build_vre_data_producers(cfg: Path | str | dict) -> list[VREDataProducer]:
    """given a VRE config (path or dict), builds the VRE Representations and turn them into robobase DataProducers"""
    representations = build_representations_from_cfg(cfg, representation_types=get_vre_repository()) # topo-sorted
    logger.debug(f"Built VRE representations: {representations}")
    res = [VREDataProducer(representation) for representation in representations]
    return res
