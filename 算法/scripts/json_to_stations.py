"""把 web/ 地图工具导出的 JSON 转成 stations.csv。

用法：
    python scripts/json_to_stations.py --input web_export.json --output data/real/stations.csv
"""
from __future__ import annotations

import argparse
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src"))

from bike_sched.entities import Station  # noqa: E402
from bike_sched.utils.geo import save_stations_csv  # noqa: E402


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--input", required=True, help="web/ 导出的 JSON")
    ap.add_argument("--output", default="data/real/stations.csv")
    ap.add_argument("--init-bikes", type=int, default=0,
                    help="首日 06:30 观测值；JSON 无此字段时使用")
    ap.add_argument("--target-ratio", type=float, default=0.5,
                    help="target_bikes = capacity × ratio（JSON 无此字段时使用）")
    args = ap.parse_args()

    with open(args.input, "r", encoding="utf-8") as f:
        obj = json.load(f)
    arr = obj["stations"] if isinstance(obj, dict) else obj
    if not isinstance(arr, list) or not arr:
        raise SystemExit("JSON 中未找到非空 stations 数组")

    stations = []
    for r in arr:
        cap = int(r.get("capacity") or 0)
        stations.append(
            Station(
                id=str(r["id"]),
                name=str(r.get("name", "")),
                lng=float(r["lng"]),
                lat=float(r["lat"]),
                capacity=cap,
                func=str(r.get("func") or "other"),
                attraction=float(r.get("attraction") or 0.5),
                init_bikes=int(r.get("init_bikes") or args.init_bikes),
                target_bikes=float(r.get("target_bikes") or cap * args.target_ratio),
            )
        )

    save_stations_csv(stations, args.output)
    print(f"[ok] {len(stations)} 个点位 -> {args.output}")


if __name__ == "__main__":
    main()
