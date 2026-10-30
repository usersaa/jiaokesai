"""训练 PPO 并评估。

用法：
    python scripts/train_ppo.py --smoke
    python scripts/train_ppo.py --timesteps 200000 --seed 0
"""
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
from bike_sched.rl.ppo import train_ppo  # noqa: E402
from bike_sched.scenario import load_scenario_from_csv, make_synthetic_scenario  # noqa: E402


def build_scenario(cfg, stations_path: str | None):
    if stations_path and os.path.exists(stations_path):
        return load_scenario_from_csv(cfg, stations_path)
    return make_synthetic_scenario(cfg)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--stations", default="data/synthetic/stations.csv")
    ap.add_argument("--timesteps", type=int, default=None)
    ap.add_argument("--seed", type=int, default=0)
    ap.add_argument("--out", default="outputs/ppo")
    ap.add_argument("--smoke", action="store_true")
    args = ap.parse_args()

    cfg = load_config(args.config)
    if args.smoke:
        cfg["ppo"]["n_steps"] = 256
        cfg["ppo"]["batch_size"] = 64
        cfg["ppo"]["net_arch"] = [64, 64]

    sc = build_scenario(cfg, args.stations)
    steps = args.timesteps if args.timesteps is not None else (
        2000 if args.smoke else int(cfg["ppo"]["total_timesteps"])
    )
    os.makedirs(args.out, exist_ok=True)
    model_path = os.path.join(args.out, f"ppo_seed{args.seed}")

    print(f"[train] stations={sc.n} steps={steps} seed={args.seed}")
    model, _ = train_ppo(cfg, sc, total_timesteps=steps, seed=args.seed,
                         save_path=model_path, verbose=0)

    policy = PPOPolicy(model)

    def env_factory():
        return CampusEnv(cfg, sc, seed=args.seed)

    rows = evaluate_policy(env_factory, policy, seeds=[101, 102, 103])
    agg = aggregate(rows)

    pd.DataFrame(rows).to_csv(os.path.join(args.out, "eval.csv"),
                              index=False, encoding="utf-8-sig")
    with open(os.path.join(args.out, "eval_summary.json"), "w", encoding="utf-8") as f:
        json.dump(agg, f, ensure_ascii=False, indent=2)

    print(json.dumps(agg, ensure_ascii=False, indent=2))
    print(f"[done] model -> {model_path}.zip")


if __name__ == "__main__":
    main()
