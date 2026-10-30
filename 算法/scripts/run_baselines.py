"""运行全部基线并输出对比表。"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from bike_sched.baselines import GreedyPolicy, NoOpPolicy, RandomPolicy, SimulatedAnnealingPolicy  # noqa: E402
from bike_sched.config import load_config  # noqa: E402
from bike_sched.env import CampusEnv  # noqa: E402
from bike_sched.rl.evaluate import aggregate, evaluate_policy  # noqa: E402
from bike_sched.scenario import load_scenario_from_csv, make_synthetic_scenario  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--stations", default="data/synthetic/stations.csv")
    ap.add_argument("--seeds", default="101,102,103")
    ap.add_argument("--out", default="outputs/baselines")
    ap.add_argument("--skip-sa", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    sc = (load_scenario_from_csv(cfg, args.stations)
          if os.path.exists(args.stations) else make_synthetic_scenario(cfg))
    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]

    def env_factory():
        return CampusEnv(cfg, sc, seed=0)

    policies = [
        NoOpPolicy(),
        RandomPolicy(seed=0),
        GreedyPolicy(allow_truck=True, allow_coupon=False, name="pure_truck"),
        GreedyPolicy(allow_truck=False, allow_coupon=True, name="pure_coupon"),
        GreedyPolicy(allow_truck=True, allow_coupon=True, name="greedy"),
    ]
    if not args.skip_sa:
        sa = SimulatedAnnealingPolicy(
            env_factory,
            iterations=int(cfg["experiment"].get("sa_iterations", 60)),
            init_temp=float(cfg["experiment"].get("sa_init_temp", 1.0)),
            cooling=float(cfg["experiment"].get("sa_cooling", 0.95)),
        )
        sa.fit()
        policies.append(sa)

    all_rows, summary = [], []
    for p in policies:
        rows = evaluate_policy(env_factory, p, seeds=seeds)
        all_rows.extend(rows)
        agg = aggregate(rows)
        agg["policy"] = p.name
        summary.append(agg)
        print(f"[{p.name}] service_rate={agg.get('service_rate', 0):.4f} "
              f"unit_cost={agg.get('unit_service_cost', 0):.4f} "
              f"shortage={agg.get('total_shortage', 0):.1f}")

    os.makedirs(args.out, exist_ok=True)
    pd.DataFrame(all_rows).to_csv(os.path.join(args.out, "baseline_rows.csv"),
                                  index=False, encoding="utf-8-sig")
    df = pd.DataFrame(summary)
    df.to_csv(os.path.join(args.out, "baseline_summary.csv"),
              index=False, encoding="utf-8-sig")
    print(df[["policy", "service_rate", "total_shortage", "unit_service_cost"]].to_string(index=False))


if __name__ == "__main__":
    main()
