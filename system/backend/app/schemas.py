from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class LoginIn(BaseModel):
    username: str
    password: str


class RegisterIn(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    display_name: str = ""
    password: str = Field(min_length=8, max_length=72)


class ChangePasswordIn(BaseModel):
    old_password: str
    new_password: str = Field(min_length=8, max_length=72)


class UserOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    username: str
    display_name: str
    role: str
    is_active: bool
    approval_status: str
    must_change_password: bool
    created_at: datetime | None = None
    last_login_at: datetime | None = None


class TokenOut(BaseModel):
    token: str
    user: UserOut


class UserCreate(BaseModel):
    username: str = Field(min_length=3, max_length=50)
    display_name: str = ""
    password: str = Field(min_length=8, max_length=72)
    role: str = "viewer"


class UserUpdate(BaseModel):
    display_name: str | None = None
    role: str | None = None
    is_active: bool | None = None


class StationIn(BaseModel):
    id: str
    name: str = ""
    lng: float
    lat: float
    capacity: int = 30
    func: str = "other"
    attraction: float = 0.5
    init_bikes: int = 0
    target_bikes: float = 0
    polygon_json: Any | None = None
    area_m2: float | None = None


class StationOut(StationIn):
    model_config = ConfigDict(from_attributes=True)


class ScenarioIn(BaseModel):
    name: str
    config_json: dict = Field(default_factory=dict)
    seed: int = 42
    model_version: str = "ppo_seed0"


class ScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    config_json: dict
    seed: int
    model_version: str
    status: str
    created_at: datetime | None = None


class SimulationCreate(BaseModel):
    scenario_id: int | None = None
    policy: str = "ppo"
    seed: int = 101
    overrides: dict = Field(default_factory=dict)


class NightCreate(BaseModel):
    scenario_id: int | None = None


class SettingIn(BaseModel):
    key: str
    value: Any
