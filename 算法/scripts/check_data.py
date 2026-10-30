"""数据质量检查（对应 docs/03 第 4 节）。

用法：
    python scripts/check_data.py --data data/real
"""
from __future__ import annotations

import argparse
import os
import sys

import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from bike_sched.utils.geo import load_stations_csv  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="data/real")
    args = ap.parse_args()

    errors, warns, info = [], [], []

    # ---------------- stations ----------------
    sp = os.path.join(args.data, "stations.csv")
    stations = []
    if not os.path.exists(sp):
        errors.append("缺少 stations.csv")
    else:
        stations = load_stations_csv(sp)
        ids = [s.id for s in stations]
        if len(ids) != len(set(ids)):
            errors.append("station id 重复")
        for s in stations:
            if s.capacity <= 0:
                errors.append(f"{s.id}: capacity <= 0")
            if not (103.5 < s.lng < 104.0 and 35.9 < s.lat < 36.3):
                warns.append(f"{s.id}: 经纬度不在校园范围 ({s.lng}, {s.lat})")
            if s.init_bikes > s.capacity:
                errors.append(f"{s.id}: init_bikes {s.init_bikes} > capacity {s.capacity}")
        info.append(f"stations: {len(stations)} 个")
        info.append(f"总容量: {sum(s.capacity for s in stations)} 辆")
        info.append(f"初始车辆: {sum(s.init_bikes for s in stations)} 辆")

    # ---------------- inventory ----------------
    ip = os.path.join(args.data, "inventory_observations.csv")
    if os.path.exists(ip):
        df = pd.read_csv(ip)
        info.append(f"inventory: {len(df)} 行")
        if len(df) == 0:
            warns.append("inventory_observations.csv 为空")
        else:
            for col in ["time", "station", "bikes"]:
                if col not in df.columns:
                    errors.append(f"inventory 缺少列 {col}")
            if {"station", "bikes"}.issubset(df.columns) and stations:
                cap = {s.id: s.capacity for s in stations}
                bad = df[df["station"].isin(cap) & (df["bikes"] > df["station"].map(cap))]
                if len(bad):
                    errors.append(f"inventory: {len(bad)} 行 bikes > capacity")
                if (df["bikes"] < 0).any():
                    errors.append("inventory: 存在负数 bikes")
            if {"time", "station"}.issubset(df.columns):
                dup = df.duplicated(subset=["time", "station"]).sum()
                if dup:
                    warns.append(f"inventory: {dup} 条重复 (time, station)")
    else:
        warns.append("未找到 inventory_observations.csv（可选）")

    # ---------------- od ----------------
    op = os.path.join(args.data, "od_observations.csv")
    if os.path.exists(op):
        od = pd.read_csv(op)
        info.append(f"od: {len(od)} 行")
        if len(od) and "trips" in od.columns and (od["trips"] < 0).any():
            errors.append("od: 存在负数 trips")
    else:
        warns.append("未找到 od_observations.csv（可选）")

    # ---------------- 输出 ----------------
    print("=" * 50)
    for s in info:
        print("  " + s)
    print("=" * 50)
    for w in warns:
        print("  [警告] " + w)
    for e in errors:
        print("  [错误] " + e)
    if not errors:
        print("  [通过] 数据质量检查通过")
    print("=" * 50)

    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
