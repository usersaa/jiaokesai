from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String

from .core.database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String(50), unique=True, index=True, nullable=False)
    password_hash = Column(String(255), nullable=False)
    display_name = Column(String(50), default="")
    role = Column(String(20), default="viewer")
    is_active = Column(Boolean, default=False)
    approval_status = Column(String(20), default="pending")
    must_change_password = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, nullable=True)


class Station(Base):
    __tablename__ = "stations"

    id = Column(String(10), primary_key=True)
    name = Column(String(50), default="")
    lng = Column(Float, nullable=False)
    lat = Column(Float, nullable=False)
    capacity = Column(Integer, default=30)
    func = Column(String(20), default="other")
    attraction = Column(Float, default=0.5)
    init_bikes = Column(Integer, default=0)
    target_bikes = Column(Float, default=0)
    polygon_json = Column(JSON, nullable=True)
    area_m2 = Column(Float, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Scenario(Base):
    __tablename__ = "scenarios"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), nullable=False)
    config_json = Column(JSON, default=dict)
    seed = Column(Integer, default=42)
    model_version = Column(String(50), default="ppo_seed0")
    status = Column(String(20), default="ready")
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class SimulationRun(Base):
    __tablename__ = "simulation_runs"

    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=True)
    status = Column(String(20), default="done")
    policy = Column(String(20), default="ppo")
    seed = Column(Integer, default=0)
    current_step = Column(Integer, default=0)
    summary_json = Column(JSON, default=dict)
    started_at = Column(DateTime, default=datetime.utcnow)
    finished_at = Column(DateTime, nullable=True)
    created_by = Column(Integer, ForeignKey("users.id"), nullable=True)


class SimulationStep(Base):
    __tablename__ = "simulation_steps"

    id = Column(Integer, primary_key=True)
    run_id = Column(Integer, ForeignKey("simulation_runs.id"), index=True)
    step = Column(Integer, index=True)
    time = Column(String(5), default="")
    inventory_json = Column(JSON, default=list)
    action_json = Column(JSON, default=dict)
    truck_json = Column(JSON, default=dict)
    metrics_json = Column(JSON, default=dict)
    reward_json = Column(JSON, default=dict)


class NightRun(Base):
    __tablename__ = "night_runs"

    id = Column(Integer, primary_key=True)
    scenario_id = Column(Integer, ForeignKey("scenarios.id"), nullable=True)
    status = Column(String(20), default="done")
    result_json = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow)


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, nullable=True)
    username = Column(String(50), default="")
    action = Column(String(50), default="")
    target = Column(String(80), default="")
    detail_json = Column(JSON, default=dict)
    ip = Column(String(45), default="")
    created_at = Column(DateTime, default=datetime.utcnow)


class Setting(Base):
    __tablename__ = "settings"

    key = Column(String(50), primary_key=True)
    value_json = Column(JSON, nullable=True)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ModelVersion(Base):
    __tablename__ = "models"

    id = Column(Integer, primary_key=True)
    name = Column(String(80), default="")
    version = Column(String(30), default="")
    path = Column(String(255), default="")
    metrics_json = Column(JSON, default=dict)
    is_active = Column(Boolean, default=True)
