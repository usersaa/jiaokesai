from __future__ import annotations

import numpy as np


def test_reset(env):
    obs, info = env.reset(seed=0)
    assert obs.shape == env.observation_space.shape
    assert obs.dtype == np.float32
    assert float(obs.min()) >= 0.0 and float(obs.max()) <= 1.0
    assert info["step"] == 0


def test_action_space(env):
    import gymnasium as gym

    if isinstance(env.action_space, gym.spaces.Discrete):
        assert env.action_space.n == 3 * env.n * 2
    else:
        assert list(env.action_space.nvec) == [3, env.n, 2]


def test_mask_shape_and_wait(env):
    env.reset(seed=0)
    m = env.action_masks()
    if env.action_encoding == "multidiscrete":
        assert m.shape == (3 + env.n + 2,)
    else:
        assert m.shape == (3 * env.n * 2,)
    assert bool(m[0]) is True  # wait 永远合法


def test_episode_length(env):
    env.reset(seed=0)
    steps = 0
    done = False
    while not done:
        obs, r, term, trunc, info = env.step([0, 0, 0])
        done = bool(term or trunc)
        steps += 1
    assert steps == env.T


def test_invalid_truck_action_falls_back(env):
    env.reset(seed=0)
    # 初始库存不紧张时，搬运动作大概率非法；非法应回落为 wait
    obs, r, term, trunc, info = env.step([1, 0, 1])
    assert info["mode"] in (0, 1, 2)
    if not info["valid"]:
        assert info["mode"] == 0


def test_inventory_conservation_bounds(env):
    env.reset(seed=0)
    for _ in range(20):
        obs, r, term, trunc, info = env.step([0, 0, 0])
        assert np.all(info["inventory"] >= -1e-6)
        assert np.all(info["inventory"] <= env.capacity + 1e-6)
        if term:
            break


def test_metrics_summary_keys(env):
    env.reset(seed=0)
    env.step([0, 0, 0])
    m = env.metrics_summary()
    for k in ["bike_shortage", "return_shortage", "truck_trips",
              "unit_service_cost", "imbalance_point", "imbalance_flow",
              "agent_shortage", "env_deficit", "service_rate"]:
        assert k in m
