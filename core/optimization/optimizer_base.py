from __future__ import annotations

from abc import ABC, abstractmethod
import numpy as np

from core.model.structure import Structure


class OptimizerBase(ABC):
    @abstractmethod
    def step(self, structure: Structure) -> np.ndarray:
        raise NotImplementedError

    @abstractmethod
    def run(self, structure: Structure, target_mass_fraction: float, max_iters: int = 200):
        raise NotImplementedError
