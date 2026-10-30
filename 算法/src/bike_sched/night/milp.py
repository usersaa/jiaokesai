"""夜间静态再平衡 MILP（建模文档 8.2 / 10.3）。

场景：23:30—06:30 制度性零需求，运维车可连续作业。
决策：各点位净调入/调出量 y_i、访问路径 x_ij、车辆载量 load_i。
目标：最小化「次日目标库存偏差 + 行驶成本」。

约定：
  - 车场为 config.night.depot_station 指定的站点（默认 P01），路径从车场出发并返回；
  - 车场自身库存不变（y_depot = 0），仅作为集散点；
  - y_i > 0 表示调入（放车），y_i < 0 表示调出（取车）；
  - 车辆从车场空载出发，返回时也必须为空载。

模型用 OR-Tools CP-SAT 求解（整数线性），12 点位规模可秒级求解。
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

import numpy as np

from ..entities import Scenario


def _default_target(cfg: Dict[str, Any], scenario: Scenario) -> np.ndarray:
    """按 target_rule 生成夜间调度目标库存。

    morning_demand：目标 = 次日 P1 峰值需求 × 缓冲系数，截断到容量。
    half_capacity ：目标 = 0.5 × 容量。
    """
    cap = scenario.capacities.astype(float)
    rule = str(cfg["night"].get("target_rule", "morning_demand")).lower()
    if rule == "morning_demand":
        from ..config import time_grid
        from ..demand import DemandModel

        p1 = next((p for p in scenario.pulses if p.id == "P1"), scenario.pulses[0])
        grid = time_grid(cfg)
        steps = [s for s, t in enumerate(grid) if p1.start_min <= t < p1.end_min]
        if not steps:
            steps = [0]
        dm = DemandModel(cfg, scenario)
        D = np.sum([dm.true_demand(s) for s in steps], axis=0)
        D = np.maximum(D, 1e-9)

        total = float(cfg["system"]["total_bikes"])
        tgt = np.minimum(D / D.sum() * total, cap)

        # 容量截断后若总和不足，把剩余车辆按空余容量分配
        deficit = total - float(tgt.sum())
        if deficit > 1e-6:
            room = cap - tgt
            if room.sum() > 1e-6:
                tgt = tgt + room * min(deficit / room.sum(), 1.0)
        return np.minimum(tgt, cap)
    return cap * 0.5


def solve_night_rebalancing(
    cfg: Dict[str, Any],
    scenario: Scenario,
    inventory: Optional[np.ndarray] = None,
    target: Optional[np.ndarray] = None,
    time_limit_s: Optional[float] = None,
    verbose: bool = False,
) -> Dict[str, Any]:
    from ortools.sat.python import cp_model

    n = scenario.n
    inv0 = (np.asarray(inventory, dtype=float) if inventory is not None
            else scenario.init_inventory().astype(float))
    tgt = (np.asarray(target, dtype=float) if target is not None
           else _default_target(cfg, scenario))
    cap = scenario.capacities.astype(int)
    C = int(cfg["truck"]["capacity"])
    DEP = int(cfg["night"].get("depot_station", 0))
    if not (0 <= DEP < n):
        raise ValueError(f"depot_station={DEP} 超出站点范围 0..{n-1}")
    v_m_per_min = float(cfg["truck"]["speed_kmh"]) * 1000.0 / 60.0
    travel_cost = float(cfg["night"].get("travel_cost_per_min", 1.0))
    inv_weight = float(cfg["night"].get("inventory_weight", 10.0))
    tl = float(time_limit_s if time_limit_s is not None
               else cfg["night"].get("time_limit_s", 30))

    model = cp_model.CpModel()

    # 站点净调入（正）/ 调出（负）；车场固定为 0
    y = [model.NewIntVar(-C, C, f"y{i}") for i in range(n)]
    u = [model.NewIntVar(0, int(cap[i]), f"u{i}") for i in range(n)]
    dev = [model.NewIntVar(0, int(cap[i]), f"dev{i}") for i in range(n)]

    for i in range(n):
        model.Add(u[i] == int(round(inv0[i])) + y[i])
        model.Add(dev[i] >= u[i] - int(round(tgt[i])))
        model.Add(dev[i] >= int(round(tgt[i])) - u[i])
    model.Add(y[DEP] == 0)
    model.Add(sum(y) == 0)

    # 路径变量
    x = {}
    for i in range(n):
        for j in range(n):
            if i != j:
                x[i, j] = model.NewBoolVar(f"x{i}_{j}")

    visited = []
    for k in range(n):
        ins = [x[i, k] for i in range(n) if i != k]
        outs = [x[k, j] for j in range(n) if j != k]
        model.Add(sum(ins) == sum(outs))
        if k == DEP:
            model.Add(sum(ins) <= 1)
        else:
            model.Add(sum(ins) <= 1)
        visited.append(sum(ins))

    # 只有被访问的站点才能有净调入/调出
    for i in range(n):
        if i == DEP:
            continue
        model.Add(y[i] <= C * visited[i])
        model.Add(y[i] >= -C * visited[i])

    # 消除子回路（MTZ），车场为起点
    order = [model.NewIntVar(0, n, f"o{i}") for i in range(n)]
    model.Add(order[DEP] == 0)
    for i in range(n):
        for j in range(n):
            if i == j or j == DEP:
                continue
            model.Add(order[j] >= order[i] + 1 - n * (1 - x[i, j]))

    # 载量平衡：load_j = load_i - y_j
    load = [model.NewIntVar(0, C, f"load{i}") for i in range(n)]
    model.Add(load[DEP] == 0)
    Mbig = 2 * C + 1
    for i in range(n):
        for j in range(n):
            if i == j:
                continue
            model.Add(load[j] >= load[i] - y[j] - Mbig * (1 - x[i, j]))
            model.Add(load[j] <= load[i] - y[j] + Mbig * (1 - x[i, j]))

    # 目标：库存偏差 + 行驶成本
    obj = int(round(inv_weight)) * sum(dev)
    for (i, j), var in x.items():
        minutes = float(scenario.dist_m[i, j]) / max(v_m_per_min, 1e-9)
        obj += int(round(travel_cost * minutes)) * var
    model.Minimize(obj)

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = tl
    solver.parameters.num_search_workers = 4
    solver.parameters.log_search_progress = bool(verbose)
    status = solver.Solve(model)
    status_name = solver.StatusName(status)

    if status not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return {
            "status": status_name,
            "feasible": False,
            "objective": None,
            "y": None,
            "u": None,
            "route": None,
            "travel_min": None,
            "depot": DEP,
        }

    y_val = [int(solver.Value(y[i])) for i in range(n)]
    u_val = [int(solver.Value(u[i])) for i in range(n)]

    # 还原路径
    route: List[int] = [DEP]
    cur = DEP
    for _ in range(n + 1):
        nxt = None
        for j in range(n):
            if j != cur and (cur, j) in x and solver.Value(x[cur, j]) == 1:
                nxt = j
                break
        if nxt is None:
            break
        route.append(nxt)
        cur = nxt
        if cur == DEP:
            break

    travel_min = 0.0
    for a, b in zip(route[:-1], route[1:]):
        travel_min += float(scenario.dist_m[a, b]) / max(v_m_per_min, 1e-9)

    return {
        "status": status_name,
        "feasible": True,
        "objective": float(solver.ObjectiveValue()),
        "y": y_val,
        "u": u_val,
        "route": route,
        "travel_min": float(travel_min),
        "depot": DEP,
        "target": tgt.tolist(),
        "inventory_before": inv0.tolist(),
    }
