"""不调度基线：永远 wait。"""
from __future__ import annotations

import numpy as np


class NoOpPolicy:
    name = "noop"

    def act(self, env, obs=None) -> np.ndarray:
        return np.array([0, 0, 0], dtype=np.int64)
