from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parents[2]
SYSTEM_DIR = BACKEND_DIR.parent
CODE_DIR = SYSTEM_DIR.parent
ALGO_DIR = CODE_DIR / "算法"

ALGO_SRC = ALGO_DIR / "src"
CONFIG_YAML = ALGO_DIR / "configs" / "default.yaml"
MODEL_PATH = ALGO_DIR / "outputs" / "ppo" / "ppo_seed0.zip"
EXPERIMENTS_CSV = ALGO_DIR / "outputs" / "experiments" / "main_summary.csv"
DB_PATH = BACKEND_DIR / "system.db"
FRONTEND_DIST = SYSTEM_DIR / "frontend" / "dist"
STATIC_DIR = BACKEND_DIR / "static"

JWT_SECRET = os.getenv("JWT_SECRET", "lzjtu-campus-ebike-2026")
JWT_ALG = "HS256"
ACCESS_TOKEN_HOURS = int(os.getenv("ACCESS_TOKEN_HOURS", "8"))

AMAP_KEY = os.getenv("AMAP_KEY", "c747dded701673039c2f37176a2b47c9")
AMAP_SECURITY = os.getenv("AMAP_SECURITY", "65fc5044e4e373f2f9ec39237c78cf8b")

DEFAULT_ADMIN = os.getenv("DEFAULT_ADMIN", "admin")
DEFAULT_ADMIN_PASSWORD = os.getenv("DEFAULT_ADMIN_PASSWORD", "admin123")
