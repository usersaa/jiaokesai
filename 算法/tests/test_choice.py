from __future__ import annotations

import numpy as np

from bike_sched.choice import ChoiceModel


def test_kappa_decreasing(cfg, scenario):
    cm = ChoiceModel(cfg, scenario)
    k = cm.kappa(np.array([0, 2, 5, 10]))
    assert np.all(np.diff(k) < 0)
    assert abs(k[0] - 1.0) < 1e-9


def test_pickup_prob(cfg, scenario):
    cm = ChoiceModel(cfg, scenario)
    f = cm.pickup_prob(np.array([0, 5, 10]), np.array([0, 5, 0]))
    assert f[0] == 0.0
    assert abs(f[1] - 0.5) < 1e-9
    assert abs(f[2] - 1.0) < 1e-9


def test_redirect_respects_capacity(cfg, scenario):
    cm = ChoiceModel(cfg, scenario)
    n = scenario.n
    unmet = np.zeros(n)
    unmet[0] = 100.0
    avail = np.zeros(n)
    avail[1] = 3.0
    extra, cost, M = cm.redirect(unmet, avail, np.zeros(n), np.zeros(n))
    assert extra[1] <= 3.0 + 1e-9
    assert M.sum() <= 100.0 + 1e-9
    assert cost >= 0.0


def test_coupon_increases_redirect(cfg, scenario):
    cm = ChoiceModel(cfg, scenario)
    n = scenario.n
    unmet = np.zeros(n)
    unmet[0] = 100.0
    avail = np.zeros(n)
    avail[1] = 50.0
    e0, c0, _ = cm.redirect(unmet, avail, np.zeros(n), np.zeros(n))
    prices = np.zeros(n)
    prices[1] = 2.0
    e1, c1, _ = cm.redirect(unmet, avail, np.zeros(n), prices)
    assert e1[1] >= e0[1] - 1e-9
    assert c1 >= 0.0
