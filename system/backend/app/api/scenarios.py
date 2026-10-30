from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_user, require_roles
from ..models import Scenario, SimulationRun, User
from ..schemas import ScenarioIn, ScenarioOut
from ..services.audit import audit

router = APIRouter(prefix="/api/scenarios", tags=["scenarios"])


@router.get("", response_model=list[ScenarioOut])
def list_scenarios(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Scenario).order_by(Scenario.id.desc()).all()


@router.get("/{scenario_id}", response_model=ScenarioOut)
def get_scenario(scenario_id: int, db: Session = Depends(get_db),
                 user: User = Depends(get_current_user)):
    scenario = db.get(Scenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="方案不存在")
    return scenario


@router.post("", response_model=ScenarioOut)
def create_scenario(payload: ScenarioIn, db: Session = Depends(get_db),
                    user: User = Depends(require_roles("admin", "operator"))):
    scenario = Scenario(
        name=payload.name,
        config_json=payload.config_json or {},
        seed=payload.seed,
        model_version=payload.model_version,
        created_by=user.id,
    )
    db.add(scenario)
    db.commit()
    db.refresh(scenario)
    audit(db, user, "create_scenario", scenario.name)
    return scenario


@router.put("/{scenario_id}", response_model=ScenarioOut)
def update_scenario(scenario_id: int, payload: ScenarioIn, db: Session = Depends(get_db),
                    user: User = Depends(require_roles("admin", "operator"))):
    scenario = db.get(Scenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="方案不存在")
    scenario.name = payload.name
    scenario.config_json = payload.config_json or {}
    scenario.seed = payload.seed
    scenario.model_version = payload.model_version
    db.commit()
    db.refresh(scenario)
    audit(db, user, "update_scenario", scenario.name)
    return scenario


@router.delete("/{scenario_id}")
def delete_scenario(scenario_id: int, db: Session = Depends(get_db),
                    user: User = Depends(require_roles("admin", "operator"))):
    scenario = db.get(Scenario, scenario_id)
    if scenario is None:
        raise HTTPException(status_code=404, detail="方案不存在")
    if db.query(SimulationRun).filter(SimulationRun.scenario_id == scenario_id).first():
        raise HTTPException(status_code=400, detail="该方案已有运行记录，不能删除")
    db.delete(scenario)
    db.commit()
    audit(db, user, "delete_scenario", scenario.name)
    return {"ok": True}
