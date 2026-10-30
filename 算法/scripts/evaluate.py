"""评估已训练模型。"""
from __future__ import annotations

import argparse
import json
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from bike_sched.config import load_config  # noqa: E402
from bike_sched.env import CampusEnv  # noqa: E402
from bike_sched.rl.evaluate import PPOPolicy, aggregate, evaluate_policy  # noqa: E402
from bike_sched.rl.ppo import load_ppo  # noqa: E402
from bike_sched.scenario import load_scenario_from_csv, make_synthetic_scenario  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--stations", default="data/synthetic/stations.csv")
    ap.add_argument("--model", required=True)
    ap.add_argument("--seeds", default="101,102,103")
    ap.add_argument("--out", default="outputs/eval")
    args = ap.parse_args()

    cfg = load_config(args.config)
    sc = (load_scenario_from_csv(cfg, args.stations)
          if os.path.exists(args.stations) else make_synthetic_scenario(cfg))
    model, _ = load_ppo(args.model, cfg, sc)
    policy = PPOPolicy(model)

    def env_factory():
        return CampusEnv(cfg, sc, seed=0)

    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    rows = evaluate_policy(env_factory, policy, seeds=seeds)
    agg = aggregate(rows)

    os.makedirs(args.out, exist_ok=True)
    pd.DataFrame(rows).to_csv(os.path.join(args.out, "eval_rows.csv"),
                              index=False, encoding="utf-8-sig")
    with open(os.path.join(args.out, "eval_summary.json"), "w", encoding="utf-8") as f:
        json.dump(agg, f, ensure_ascii=False, indent=2)
    print(json.dumps(agg, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
