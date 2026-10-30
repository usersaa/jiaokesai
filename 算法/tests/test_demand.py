from __future__ import annotations

import numpy as np

from bike_sched.demand import DemandModel


def test_demand_non_negative(cfg, scenario):
    dm = DemandModel(cfg, scenario)
    D = dm.demand_matrix(30)
    assert D.shape == (30, scenario.n)
    assert np.all(D >= 0)


def test_od_rows_sum_to_one(cfg, scenario):
    dm = DemandModel(cfg, scenario)
    P = dm.od_probabilities()
    assert np.allclose(P.sum(axis=1), 1.0)
    assert np.allclose(np.diag(P), 0.0)


def test_pulse_peak_higher_than_baseline(cfg, scenario):
    dm = DemandModel(cfg, scenario)
    # P1 峰值 07:50 附近应显著高于清晨 06:30
    idx_0630 = 0
    idx_0750 = 8
    assert dm.true_demand(idx_0750).sum() > 3 * dm.true_demand(idx_0630).sum()


def test_realized_od_truncated(cfg, scenario):
    dm = DemandModel(cfg, scenario)
    D = np.full(scenario.n, 10.0)
    od = dm.od_matrix(D)
    borrowed = np.full(scenario.n, 5.0)
    r_od = dm.realized_od(od, borrowed, D)
    assert np.allclose(r_od.sum(axis=1), 5.0)
