from __future__ import annotations

import numpy as np

from bike_sched.supply import SupplyModel


def test_available(cfg, scenario):
    sm = SupplyModel(cfg, scenario)
    n = np.array([0, 1, 10, 100])
    a = sm.available(n)
    assert a[0] == 0
    assert np.all(a <= n)


def test_borrow_and_shortage(cfg, scenario):
    sm = SupplyModel(cfg, scenario)
    D = np.array([5.0, 10.0, 0.0])
    avail = np.array([3, 10, 0])
    b, e = sm.borrow(D, avail)
    assert np.allclose(b, [3, 10, 0])
    assert np.allclose(e, [2, 0, 0])


def test_return_shortage(cfg, scenario):
    sm = SupplyModel(cfg, scenario)
    ret = np.array([5.0, 0.0])
    free = np.array([2.0, 10.0])
    e = sm.return_shortage(ret, free)
    assert np.allclose(e, [3.0, 0.0])


def test_truck_time(cfg, scenario):
    sm = SupplyModel(cfg, scenario)
    t = sm.truck_service_min(0, 1, 10)
    assert t > 0
    assert t >= 10 * sm.load_min
    assert sm.busy_steps(t) >= 1
