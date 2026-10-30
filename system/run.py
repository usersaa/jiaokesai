from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
BACKEND = ROOT / "backend"
sys.path.insert(0, str(BACKEND))
os.chdir(BACKEND)

try:
    import uvicorn  # noqa: E402
except ModuleNotFoundError:
    print("=" * 66)
    print("当前 Python 缺少 fastapi / uvicorn，系统无法启动。")
    print("请使用项目虚拟环境：")
    print(r"  C:\Users\Fasder\.workbuddy-ai\binaries\python\envs\bike_sched\Scripts\python.exe system\run.py")
    print("或直接双击：system\\start.bat")
    print("=" * 66)
    raise SystemExit(1)

if __name__ == "__main__":
    print("校园共享电单车调度系统：http://127.0.0.1:8000")
    uvicorn.run("app.main:app", host="127.0.0.1", port=8000, reload=False)
