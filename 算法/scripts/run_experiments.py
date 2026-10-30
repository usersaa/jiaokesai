"""实验入口：主实验、消融、参数敏感性、泛化。

用法：
    python scripts/run_experiments.py --exp main --model outputs/ppo/ppo_seed0
    python scripts/run_experiments.py --exp ablation --model ...
    python scripts/run_experiments.py --exp sensitivity --model ...
    python scripts/run_experiments.py --exp generalization --timesteps 50000
    python scripts/run_experiments.py --exp all --model ...
"""
from __future__ import annotations

import argparse
import copy
import json
import os
import sys
from typing import Any, Dict, List, Optional

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

import matplotlib  # noqa: E402
matplotlib.use("Agg")
import matplotlib.pyplot as plt  # noqa: E402

from bike_sched.baselines import GreedyPolicy, NoOpPolicy, RandomPolicy, SimulatedAnnealingPolicy  # noqa: E402
from bike_sched.config import deep_update, load_config  # noqa: E402
from bike_sched.env import CampusEnv  # noqa: E402
from bike_sched.rl.evaluate import PPOPolicy, aggregate, evaluate_policy  # noqa: E402
from bike_sched.rl.ppo import load_ppo, train_ppo  # noqa: E402
from bike_sched.scenario import load_scenario_from_csv, make_synthetic_scenario  # noqa: E402

plt.rcParams["font.sans-serif"] = ["Microsoft YaHei", "SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


# ------------------------------------------------------------
def get_scenario(cfg, stations_path: Optional[str]):
    if stations_path and os.path.exists(stations_path):
        return load_scenario_from_csv(cfg, stations_path)
    return make_synthetic_scenario(cfg)


def env_factory_for(cfg, sc, seed: int = 0):
    def _f():
        return CampusEnv(cfg, sc, seed=seed)
    return _f


def build_policies(cfg, sc, model_path: Optional[str], include_sa: bool = False):
    policies = [
        NoOpPolicy(),
        RandomPolicy(seed=0),
        GreedyPolicy(allow_truck=True, allow_coupon=False, name="pure_truck"),
        GreedyPolicy(allow_truck=False, allow_coupon=True, name="pure_coupon"),
        GreedyPolicy(allow_truck=True, allow_coupon=True, name="greedy"),
    ]
    if include_sa:
        sa = SimulatedAnnealingPolicy(
            env_factory_for(cfg, sc, 0),
            iterations=int(cfg["experiment"].get("sa_iterations", 60)),
            init_temp=float(cfg["experiment"].get("sa_init_temp", 1.0)),
            cooling=float(cfg["experiment"].get("sa_cooling", 0.95)),
        )
        sa.fit()
        policies.append(sa)
    if model_path:
        model, _ = load_ppo(model_path, cfg, sc)
        policies.append(PPOPolicy(model))
    return policies


def run_policy_set(cfg, sc, policies, seeds: List[int], out_dir: str, tag: str) -> pd.DataFrame:
    os.makedirs(out_dir, exist_ok=True)
    all_rows, summary = [], []
    for p in policies:
        rows = evaluate_policy(env_factory_for(cfg, sc, 0), p, seeds=seeds)
        all_rows.extend(rows)
        agg = aggregate(rows)
        agg["policy"] = p.name
        summary.append(agg)
        print(f"  [{p.name:12s}] service={agg.get('service_rate', 0):.4f} "
              f"shortage={agg.get('total_shortage', 0):7.1f} "
              f"cost={agg.get('unit_service_cost', 0):.4f}")
    pd.DataFrame(all_rows).to_csv(os.path.join(out_dir, f"{tag}_rows.csv"),
                                  index=False, encoding="utf-8-sig")
    df = pd.DataFrame(summary)
    df.to_csv(os.path.join(out_dir, f"{tag}_summary.csv"), index=False, encoding="utf-8-sig")
    return df


def plot_bar(df: pd.DataFrame, out_dir: str, tag: str) -> None:
    metrics = [
        ("service_rate", "服务率", "service_rate"),
        ("total_shortage", "总短缺（次）", "total_shortage"),
        ("unit_service_cost", "单位服务成本（元/单）", "unit_cost"),
        ("truck_trips", "搬运趟次", "truck_trips"),
    ]
    fig, axes = plt.subplots(2, 2, figsize=(11, 7))
    for ax, (col, title, _) in zip(axes.ravel(), metrics):
        if col not in df.columns:
            continue
        ax.bar(df["policy"], df[col], color="#2f6f9f")
        ax.set_title(title)
        ax.tick_params(axis="x", rotation=25)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, f"{tag}_bar.png"), dpi=160)
    plt.close(fig)


# ------------------------------------------------------------
def exp_main(cfg, sc, model_path, seeds, out_dir):
    print("[main] 基线 + PPO")
    policies = build_policies(cfg, sc, model_path, include_sa=True)
    df = run_policy_set(cfg, sc, policies, seeds, out_dir, "main")
    plot_bar(df, out_dir, "main")
    return df


def exp_ablation(cfg, sc, model_path, seeds, out_dir):
    print("[ablation] 去发券 / 去搬运 / 协同")
    policies = [
        GreedyPolicy(allow_truck=True, allow_coupon=False, name="pure_truck"),
        GreedyPolicy(allow_truck=False, allow_coupon=True, name="pure_coupon"),
        GreedyPolicy(allow_truck=True, allow_coupon=True, name="greedy"),
    ]
    if model_path:
        model, _ = load_ppo(model_path, cfg, sc)
        policies.append(PPOPolicy(model))
    df = run_policy_set(cfg, sc, policies, seeds, out_dir, "ablation")
    plot_bar(df, out_dir, "ablation")
    return df


def exp_sensitivity(cfg, sc, model_path, seeds, out_dir):
    print("[sensitivity] lambda / VOT / gamma / rho_soc")
    grids = {
        "lambda_per_min": ("choice", [0.05, 0.10, 0.15, 0.20, 0.30]),
        "vot_yuan_per_min": ("choice", [0.2, 0.35, 0.5, 0.8, 1.2]),
        "gamma_single_ride": ("system", [0.1, 0.2, 0.35, 0.5, 0.7]),
        "rho_soc": ("system", [0.6, 0.7, 0.85, 0.95, 1.0]),
    }
    rows = []
    for key, (section, values) in grids.items():
        for v in values:
            cfg_i = copy.deepcopy(cfg)
            cfg_i[section][key] = v
            sc_i = make_synthetic_scenario(cfg_i) if not os.path.exists("data/synthetic/stations.csv") \
                else load_scenario_from_csv(cfg_i, "data/synthetic/stations.csv")
            policies = [NoOpPolicy(), GreedyPolicy(name="greedy")]
            if model_path:
                model, _ = load_ppo(model_path, cfg_i, sc_i)
                policies.append(PPOPolicy(model))
            for p in policies:
                m = aggregate(evaluate_policy(env_factory_for(cfg_i, sc_i, 0), p, seeds=seeds))
                rows.append({
                    "param": key, "value": v, "policy": p.name,
                    "service_rate": m.get("service_rate", 0),
                    "total_shortage": m.get("total_shortage", 0),
                    "unit_service_cost": m.get("unit_service_cost", 0),
                })
    df = pd.DataFrame(rows)
    os.makedirs(out_dir, exist_ok=True)
    df.to_csv(os.path.join(out_dir, "sensitivity.csv"), index=False, encoding="utf-8-sig")

    fig, axes = plt.subplots(1, 3, figsize=(14, 4))
    for ax, metric in zip(axes, ["service_rate", "total_shortage", "unit_service_cost"]):
        for param in grids:
            sub = df[df["param"] == param]
            if sub.empty:
                continue
            ax.plot(sub["value"], sub[metric], marker="o", label=param)
        ax.set_xlabel("参数取值")
        ax.set_title(metric)
        ax.legend(fontsize=8)
    fig.tight_layout()
    fig.savefig(os.path.join(out_dir, "sensitivity.png"), dpi=160)
    plt.close(fig)
    return df


def exp_generalization(cfg, sc, timesteps, out_dir):
    print("[generalization] 训练 4 个随机种子，留出第 5 个种子测试")
    os.makedirs(out_dir, exist_ok=True)
    rows = []
    for seed in [0, 1, 2, 3]:
        model, _ = train_ppo(cfg, sc, total_timesteps=timesteps, seed=seed)
        policy = PPOPolicy(model)
        m = aggregate(evaluate_policy(env_factory_for(cfg, sc, 0), policy, seeds=[404]))
        m["train_seed"] = seed
        rows.append(m)
        print(f"  train_seed={seed} -> service={m.get('service_rate', 0):.4f} "
              f"shortage={m.get('total_shortage', 0):.1f}")
    df = pd.DataFrame(rows)
    df.to_csv(os.path.join(out_dir, "generalization.csv"), index=False, encoding="utf-8-sig")
    return df


# ------------------------------------------------------------
def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default="configs/default.yaml")
    ap.add_argument("--stations", default="data/synthetic/stations.csv")
    ap.add_argument("--model", default=None, help="PPO 模型路径（不含 .zip）")
    ap.add_argument("--seeds", default="101,102,103")
    ap.add_argument("--exp", default="main",
                    choices=["main", "ablation", "sensitivity", "generalization", "all"])
    ap.add_argument("--timesteps", type=int, default=50000)
    ap.add_argument("--out", default="outputs/experiments")
    args = ap.parse_args()

    cfg = load_config(args.config)
    sc = get_scenario(cfg, args.stations)
    seeds = [int(x) for x in args.seeds.split(",") if x.strip()]
    os.makedirs(args.out, exist_ok=True)

    if args.exp in ("main", "all"):
        exp_main(cfg, sc, args.model, seeds, args.out)
    if args.exp in ("ablation", "all"):
        exp_ablation(cfg, sc, args.model, seeds, args.out)
    if args.exp in ("sensitivity", "all"):
        exp_sensitivity(cfg, sc, args.model, seeds, args.out)
    if args.exp in ("generalization", "all"):
        exp_generalization(cfg, sc, args.timesteps, args.out)

    print(f"[done] -> {args.out}")


if __name__ == "__main__":
    main()
