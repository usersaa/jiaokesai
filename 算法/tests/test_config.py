from __future__ import annotations

from bike_sched.config import fmt_hhmm, n_steps, parse_hhmm, time_grid


def test_parse_hhmm():
    assert parse_hhmm("06:30") == 390
    assert parse_hhmm("23:30") == 1410
    assert fmt_hhmm(390) == "06:30"


def test_time_grid(cfg):
    g = time_grid(cfg)
    assert len(g) == n_steps(cfg)
    assert fmt_hhmm(g[0]) == "06:30"
    assert fmt_hhmm(g[-1]) == "23:20"
    assert all(b - a == 10 for a, b in zip(g[:-1], g[1:]))


def test_pulses(cfg, scenario):
    assert len(scenario.pulses) == 7
    ids = [p.id for p in scenario.pulses]
    assert ids == [f"P{i}" for i in range(1, 8)]
    assert all(p.start_min < p.peak_min < p.end_min for p in scenario.pulses)
