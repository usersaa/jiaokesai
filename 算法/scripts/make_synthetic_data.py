"""生成合成占位数据，保证全链路可跑通。

输出：
  data/synthetic/stations.csv        12 个占位 P 点
  data/synthetic/demand_by_step.csv  每步每点真实需求（模型生成，非观测）
  data/synthetic/templates/*.csv     供实地采集使用的空模板

注意：这些数据仅用于代码自检与流程演示，不能作为论文实证数据。
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from bike_sched.config import fmt_hhmm, load_config, time_grid  # noqa: E402
from bike_sched.demand import DemandModel  # noqa: E402
from bike_sched.scenario import make_synthetic_scenario  # noqa: E402
from bike_sched.utils.geo import save_stations_csv  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--out", default="data/synthetic")
    args = ap.parse_args()

    cfg = load_config(args.config)
    sc = make_synthetic_scenario(cfg)
    os.makedirs(args.out, exist_ok=True)

    # 1) 站点
    save_stations_csv(sc.stations, os.path.join(args.out, "stations.csv"))

    # 2) 模型生成的逐步需求（用于自检，不是观测数据）
    dm = DemandModel(cfg, sc)
    rows = []
    for s, t in enumerate(time_grid(cfg)):
        D = dm.true_demand(s)
        for i, st in enumerate(sc.stations):
            rows.append({
                "step": s,
                "time": fmt_hhmm(t),
                "station": st.id,
                "demand": round(float(D[i]), 4),
            })
    pd.DataFrame(rows).to_csv(
        os.path.join(args.out, "demand_by_step.csv"), index=False, encoding="utf-8-sig"
    )

    # 3) 采集模板（空）
    tpl = os.path.join(args.out, "templates")
    os.makedirs(tpl, exist_ok=True)
    pd.DataFrame(columns=["time", "station", "bikes", "note"]).to_csv(
        os.path.join(tpl, "inventory_observations.csv"), index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(columns=["time_window", "origin", "destination", "trips", "note"]).to_csv(
        os.path.join(tpl, "od_observations.csv"), index=False, encoding="utf-8-sig"
    )
    pd.DataFrame(columns=["station", "lng", "lat", "capacity", "func", "note"]).to_csv(
        os.path.join(tpl, "stations_template.csv"), index=False, encoding="utf-8-sig"
    )

    print(f"[ok] 站点 {sc.n} 个，写入 {args.out}/stations.csv")
    print(f"[ok] 逐步需求 {len(rows)} 行，写入 {args.out}/demand_by_step.csv")
    print(f"[ok] 采集模板写入 {tpl}/")


if __name__ == "__main__":
    main()
