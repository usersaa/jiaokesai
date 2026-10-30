from __future__ import annotations

import numpy as np

from bike_sched.metrics import EpisodeMetrics, distance_weight_matrix


def test_metrics_summary(cfg):
    m = EpisodeMetrics()
    n = 3
    m.add_step(
        demand=np.array([5.0, 5.0, 5.0]),
        served=10.0,
        e_b=np.array([1.0, 0.0, 0.0]),
        e_r=np.array([0.0, 2.0, 0.0]),
        n_avail=np.array([3, 5, 4]),
        free_space=np.array([3, 3, 3]),
        od=np.ones((n, n)) * 0.5,
        agent_shortage=0.5,
        env_deficit=2.5,
        truck_time=5.0,
        truck_trip=1,
        coupon_cost=1.0,
        dist_weight=distance_weight_matrix(np.array([[0, 100, 200], [100, 0, 100], [200, 100, 0]], dtype=float)),
    )
    s = m.summary(cfg)
    assert s["total_shortage"] == 3.0
    assert s["truck_trips"] == 1
    assert s["service_rate"] > 0
    assert s["imbalance_point"] > 0
    assert s["imbalance_flow"] > 0


def test_distance_weight():
    d = np.array([[0.0, 400.0], [400.0, 0.0]])
    w = distance_weight_matrix(d, alpha_m=400.0)
    assert abs(w[0, 1] - 0.5) < 1e-6
