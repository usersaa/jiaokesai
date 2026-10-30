"""pytest 共享夹具。"""
from __future__ import annotations

import os
import sys

import pytest

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "src"))

from bike_sched.config import load_config  # noqa: E402
from bike_sched.scenario import make_synthetic_scenario  # noqa: E402


@pytest.fixture(scope="session")
def cfg():
    return load_config(os.path.join(ROOT, "configs", "default.yaml"))


@pytest.fixture(scope="session")
def scenario(cfg):
    return make_synthetic_scenario(cfg)


@pytest.fixture()
def env(cfg, scenario):
    from bike_sched.env import CampusEnv

    return CampusEnv(cfg, scenario, seed=0)
