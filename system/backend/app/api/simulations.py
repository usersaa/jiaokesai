from __future__ import annotations

import csv
import io
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_user
from ..models import Scenario, SimulationRun, SimulationStep, Station, User
from ..schemas import SimulationCreate
from ..services.algorithm import run_day, station_dicts
from ..services.audit import audit

router = APIRouter(prefix="/api/simulations", tags=["simulations"])


@router.post("")
def create_simulation(payload: SimulationCreate, db: Session = Depends(get_db),
                      user: User = Depends(get_current_user)):
    stations = [s for s in db.query(Station).order_by(Station.id).all() if s.func != "nopark"]
    if len(stations) < 3:
        raise HTTPException(status_code=400, detail="点位数不足，至少需要 3 个点位")

    scenario = db.get(Scenario, payload.scenario_id) if payload.scenario_id else None
    base = dict(scenario.config_json or {}) if scenario else {}
    policy = payload.policy or base.get("policy", "ppo")
    seed = int(payload.seed if payload.seed is not None else (scenario.seed if scenario else 101))
    overrides = {
        k: v for k, v in {**base, **(payload.overrides or {})}.items()
        if k not in ("policy", "seed")
    }

    steps, summary, cfg = run_day(stations, policy_name=policy, seed=seed, overrides=overrides)

    run = SimulationRun(
        scenario_id=scenario.id if scenario else None,
        status="done",
        policy=policy,
        seed=seed,
        current_step=len(steps) - 1,
        summary_json=summary,
        created_by=user.id,
        finished_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    db.refresh(run)

    for s in steps:
        db.add(SimulationStep(
            run_id=run.id,
            step=s["step"],
            time=s["time"],
            inventory_json=s["inventory"],
            action_json=s["action"],
            truck_json=s["truck"],
            metrics_json=s["metrics"],
            reward_json=s["reward"],
        ))
    db.commit()
    audit(db, user, "run_simulation", f"run:{run.id}",
          {"policy": policy, "seed": seed})

    return {
        "run_id": run.id,
        "policy": policy,
        "seed": seed,
        "summary": summary,
        "steps": steps,
        "stations": station_dicts(stations),
        "config": {
            "lambda_per_min": cfg["choice"]["lambda_per_min"],
            "vot_yuan_per_min": cfg["choice"]["vot_yuan_per_min"],
            "gamma_single_ride": cfg["system"]["gamma_single_ride"],
            "rho_soc": cfg["system"]["rho_soc"],
        },
    }


@router.get("")
def list_runs(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    runs = db.query(SimulationRun).order_by(SimulationRun.id.desc()).limit(20).all()
    return [
        {
            "id": r.id,
            "scenario_id": r.scenario_id,
            "policy": r.policy,
            "seed": r.seed,
            "status": r.status,
            "summary": r.summary_json,
            "started_at": r.started_at.isoformat() if r.started_at else None,
            "finished_at": r.finished_at.isoformat() if r.finished_at else None,
        }
        for r in runs
    ]


@router.get("/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    run = db.get(SimulationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return {
        "id": run.id,
        "policy": run.policy,
        "seed": run.seed,
        "status": run.status,
        "summary": run.summary_json,
    }


@router.get("/{run_id}/steps")
def get_steps(run_id: int, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    rows = (db.query(SimulationStep)
            .filter(SimulationStep.run_id == run_id)
            .order_by(SimulationStep.step)
            .all())
    if not rows:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    return [
        {
            "step": r.step,
            "time": r.time,
            "inventory": r.inventory_json,
            "action": r.action_json,
            "truck": r.truck_json,
            "metrics": r.metrics_json,
            "reward": r.reward_json,
        }
        for r in rows
    ]


@router.get("/{run_id}/export")
def export_run(run_id: int, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    run = db.get(SimulationRun, run_id)
    if run is None:
        raise HTTPException(status_code=404, detail="运行记录不存在")
    rows = (db.query(SimulationStep)
            .filter(SimulationStep.run_id == run_id)
            .order_by(SimulationStep.step)
            .all())
    stations = [s for s in db.query(Station).order_by(Station.id).all() if s.func != "nopark"]

    output = io.StringIO()
    writer = csv.writer(output)
    header = ["step", "time", "action", "station", "truck_station", "truck_load",
              "service_rate", "total_shortage", "unit_service_cost", "truck_trips"]
    header += [f"inv_{s.id}" for s in stations]
    writer.writerow(header)
    for r in rows:
        action = r.action_json or {}
        truck = r.truck_json or {}
        metrics = r.metrics_json or {}
        writer.writerow([
            r.step, r.time, action.get("label", ""), action.get("station", ""),
            truck.get("station", ""), truck.get("load", ""),
            metrics.get("service_rate", ""), metrics.get("total_shortage", ""),
            metrics.get("unit_service_cost", ""), metrics.get("truck_trips", ""),
            *[v for v in (r.inventory_json or [])],
        ])
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f"attachment; filename=run_{run_id}.csv"},
    )
