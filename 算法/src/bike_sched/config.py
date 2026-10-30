"""配置加载与时间轴工具。

所有参数集中在 configs/default.yaml，代码中不出现魔法数字。
"""
from __future__ import annotations

import copy
import os
from typing import Any, Dict, List

import yaml

from .entities import Pulse

_DEFAULT_PATH = os.path.join(
    os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))),
    "configs", "default.yaml",
)


def load_config(path: str | None = None) -> Dict[str, Any]:
    """读取 YAML 配置；path 为空时读取 configs/default.yaml。"""
    p = path or _DEFAULT_PATH
    with open(p, "r", encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    return cfg


def deep_update(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    """递归合并配置（override 覆盖 base），返回新字典。"""
    out = copy.deepcopy(base)
    for k, v in (override or {}).items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = deep_update(out[k], v)
        else:
            out[k] = copy.deepcopy(v)
    return out


def parse_hhmm(s: str) -> int:
    """'07:40' -> 460（当日分钟数）。"""
    hh, mm = str(s).strip().split(":")
    return int(hh) * 60 + int(mm)


def fmt_hhmm(minute: int) -> str:
    minute = int(round(minute)) % (24 * 60)
    return f"{minute // 60:02d}:{minute % 60:02d}"


def time_grid(cfg: Dict[str, Any]) -> List[int]:
    """日内决策步的起始分钟列表（含起点，不含终点）。"""
    t = cfg["time"]
    start = parse_hhmm(t["day_start"])
    end = parse_hhmm(t["day_end"])
    step = int(t["step_minutes"])
    if end <= start:
        end += 24 * 60
    return list(range(start, end, step))


def n_steps(cfg: Dict[str, Any]) -> int:
    return len(time_grid(cfg))


def step_of_minute(cfg: Dict[str, Any], minute: int) -> int:
    """把当日分钟映射到决策步索引；超出范围返回 -1。"""
    grid = time_grid(cfg)
    if minute < grid[0] or minute >= grid[-1] + int(cfg["time"]["step_minutes"]):
        return -1
    return int((minute - grid[0]) // int(cfg["time"]["step_minutes"]))


def pulses_from_config(cfg: Dict[str, Any]) -> List[Pulse]:
    out: List[Pulse] = []
    for p in cfg["demand"]["pulses"]:
        out.append(
            Pulse(
                id=str(p["id"]),
                start_min=parse_hhmm(p["start"]),
                peak_min=parse_hhmm(p["peak"]),
                end_min=parse_hhmm(p["end"]),
                width_min=float(p["width_min"]),
                label=str(p.get("label", "")),
            )
        )
    return out


def save_config(cfg: Dict[str, Any], path: str) -> None:
    os.makedirs(os.path.dirname(os.path.abspath(path)), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        yaml.safe_dump(cfg, f, allow_unicode=True, sort_keys=False)
