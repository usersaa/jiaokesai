"""PPO 训练（Stable-Baselines3 + sb3-contrib 动作掩码）。

说明：SB3 的 MlpPolicy 提供共享主干（net_arch 共享层）+ 策略/价值双头，
与 Staffolani 2025 的共享网络结构一致；动作掩码使用 sb3-contrib 的
MaskablePPO，保证 wait/搬运/发券的非法组合不会被采样。
"""
from __future__ import annotations

import os
from typing import Any, Dict, Optional

from ..env import CampusEnv
from ..scenario import Scenario


def make_masked_env(cfg: Dict[str, Any], scenario: Scenario, seed: int = 0):
    from sb3_contrib.common.wrappers import ActionMasker

    env = CampusEnv(cfg, scenario, seed=seed)
    return ActionMasker(env, lambda e: e.unwrapped.action_masks())


def build_model(cfg: Dict[str, Any], scenario: Scenario, seed: int = 0, verbose: int = 0):
    from sb3_contrib import MaskablePPO

    env = make_masked_env(cfg, scenario, seed=seed)
    p = cfg["ppo"]
    kwargs = dict(
        learning_rate=float(p["learning_rate"]),
        n_steps=int(p["n_steps"]),
        batch_size=int(p["batch_size"]),
        gamma=float(p["gamma"]),
        gae_lambda=float(p["gae_lambda"]),
        clip_range=float(p["clip_range"]),
        ent_coef=float(p["ent_coef"]),
        vf_coef=float(p["vf_coef"]),
        max_grad_norm=float(p["max_grad_norm"]),
        policy_kwargs=dict(net_arch=list(p["net_arch"])),
        seed=int(seed),
        verbose=verbose,
        device=str(p.get("device", "auto")),
    )
    model = MaskablePPO(str(p.get("policy", "MlpPolicy")), env, **kwargs)
    return model, env


def train_ppo(
    cfg: Dict[str, Any],
    scenario: Scenario,
    total_timesteps: Optional[int] = None,
    seed: int = 0,
    save_path: Optional[str] = None,
    verbose: int = 0,
):
    model, env = build_model(cfg, scenario, seed=seed, verbose=verbose)
    steps = int(total_timesteps if total_timesteps is not None else cfg["ppo"]["total_timesteps"])
    model.learn(total_timesteps=steps, progress_bar=False)
    if save_path:
        os.makedirs(os.path.dirname(os.path.abspath(save_path)), exist_ok=True)
        model.save(save_path)
    return model, env


def load_ppo(path: str, cfg: Dict[str, Any], scenario: Scenario):
    from sb3_contrib import MaskablePPO

    env = make_masked_env(cfg, scenario, seed=0)
    model = MaskablePPO.load(path, env=env)
    return model, env
