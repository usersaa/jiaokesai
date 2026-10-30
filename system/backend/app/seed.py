from __future__ import annotations

import csv
from datetime import datetime

from .core.config import ALGO_DIR, DEFAULT_ADMIN, DEFAULT_ADMIN_PASSWORD, MODEL_PATH
from .core.database import Base, SessionLocal, engine
from .core.security import hash_password
from .models import ModelVersion, Scenario, Setting, Station, User


def init_db() -> None:
    Base.metadata.create_all(bind=engine)


def seed_data() -> None:
    db = SessionLocal()
    try:
        if db.query(User).first() is None:
            db.add(User(
                username=DEFAULT_ADMIN,
                password_hash=hash_password(DEFAULT_ADMIN_PASSWORD),
                display_name="系统管理员",
                role="admin",
                is_active=True,
                approval_status="approved",
                must_change_password=True,
            ))
            db.commit()

        stations_seeded = db.get(Setting, "stations_seeded")
        if stations_seeded is None:
            if db.query(Station).first() is None:
                csv_path = ALGO_DIR / "data" / "synthetic" / "stations.csv"
                if csv_path.exists():
                    with open(csv_path, "r", encoding="utf-8-sig", newline="") as f:
                        for row in csv.DictReader(f):
                            db.add(Station(
                                id=str(row["id"]).strip(),
                                name=str(row.get("name", "")).strip(),
                                lng=float(row["lng"]),
                                lat=float(row["lat"]),
                                capacity=int(float(row.get("capacity", 30) or 30)),
                                func=str(row.get("func", "other") or "other"),
                                attraction=float(row.get("attraction", 0.5) or 0.5),
                                init_bikes=int(float(row.get("init_bikes", 0) or 0)),
                                target_bikes=float(row.get("target_bikes", 0) or 0),
                            ))
            db.add(Setting(key="stations_seeded", value_json=True))
            db.commit()

        if db.query(Scenario).first() is None:
            db.add(Scenario(
                name="日常调度方案",
                config_json={"policy": "ppo", "seed": 101},
                seed=101,
                model_version="ppo_seed0",
                status="ready",
                created_by=1,
            ))
            db.commit()

        defaults = {
            "system_name": "共享单车调度中心",
            "self_registration": True,
            "default_policy": "ppo",
            "map_style": "normal",
        }
        for key, value in defaults.items():
            if db.get(Setting, key) is None:
                db.add(Setting(key=key, value_json=value))
        db.commit()

        if db.query(ModelVersion).first() is None:
            db.add(ModelVersion(
                name="ppo_seed0",
                version="v1",
                path=str(MODEL_PATH),
                metrics_json={},
                is_active=True,
            ))
            db.commit()
    finally:
        db.close()
