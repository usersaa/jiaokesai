from __future__ import annotations

from bike_sched.baselines import GreedyPolicy, NoOpPolicy, RandomPolicy
from bike_sched.rl.evaluate import run_episode


def test_noop_episode(env):
    m = run_episode(env, NoOpPolicy(), seed=1)
    assert m["steps"] == env.T
    assert m["truck_trips"] == 0


def test_greedy_episode(env):
    m = run_episode(env, GreedyPolicy(), seed=1)
    assert m["steps"] == env.T
    assert m["service_rate"] >= 0


def test_pure_truck_and_coupon(env):
    m1 = run_episode(env, GreedyPolicy(allow_coupon=False, name="pure_truck"), seed=1)
    m2 = run_episode(env, GreedyPolicy(allow_truck=False, name="pure_coupon"), seed=1)
    assert m1["coupon_cost_yuan"] == 0.0
    assert m2["truck_trips"] == 0


def test_random_episode(env):
    m = run_episode(env, RandomPolicy(seed=0), seed=1)
    assert m["steps"] == env.T
