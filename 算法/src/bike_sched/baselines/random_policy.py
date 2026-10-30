"""随机基线：从合法动作集中均匀采样。"""
from __future__ import annotations

import numpy as np


class RandomPolicy:
    name = "random"

    def __init__(self, seed: int = 0):
        self.rng = np.random.default_rng(seed)

    def act(self, env, obs=None) -> np.ndarray:
        mask = env.valid_action_mask_flat()
        valid = np.flatnonzero(mask)
        if valid.size == 0:
            return np.array([0, 0, 0], dtype=np.int64)
        idx = int(self.rng.choice(valid))
        n = env.n
        mode = idx // (n * 2)
        rem = idx % (n * 2)
        station = rem // 2
        tier = rem % 2
        return np.array([mode, station, tier], dtype=np.int64)
