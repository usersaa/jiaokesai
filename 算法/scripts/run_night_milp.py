"""求解夜间静态再平衡 MILP。"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from bike_sched.config import load_config  # noqa: E402
from bike_sched.night import solve_night_rebalancing  # noqa: E402
from bike_sched.scenario import load_scenario_from_csv, make_synthetic_scenario  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--stations", default="data/synthetic/stations.csv")
    ap.add_argument("--time-limit", type=float, default=None)
    ap.add_argument("--out", default="outputs/night")
    args = ap.parse_args()

    cfg = load_config(args.config)
    sc = (load_scenario_from_csv(cfg, args.stations)
          if os.path.exists(args.stations) else make_synthetic_scenario(cfg))

    res = solve_night_rebalancing(cfg, sc, time_limit_s=args.time_limit, verbose=True)
    print(json.dumps({k: v for k, v in res.items() if k != "target"}, ensure_ascii=False, indent=2))

    os.makedirs(args.out, exist_ok=True)
    with open(os.path.join(args.out, "night_result.json"), "w", encoding="utf-8") as f:
        json.dump(res, f, ensure_ascii=False, indent=2)
    print(f"[done] -> {args.out}/night_result.json")


if __name__ == "__main__":
    main()
