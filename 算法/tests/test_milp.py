from __future__ import annotations

import numpy as np

from bike_sched.night import solve_night_rebalancing


def test_night_milp_feasible(cfg, scenario):
    res = solve_night_rebalancing(cfg, scenario, time_limit_s=15)
    assert res["feasible"] is True
    assert res["status"] in ("OPTIMAL", "FEASIBLE")
    y = np.array(res["y"], dtype=float)
    u = np.array(res["u"], dtype=float)
    assert abs(y.sum()) < 1e-6
    assert np.all(u >= 0)
    assert np.all(u <= scenario.capacities + 1e-6)
    assert res["route"][0] == int(cfg["night"]["depot_station"])
    assert res["route"][-1] == int(cfg["night"]["depot_station"])
