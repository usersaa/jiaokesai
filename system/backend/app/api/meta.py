from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Body, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..core.config import AMAP_KEY, AMAP_SECURITY
from ..core.database import get_db
from ..core.security import get_current_user, require_roles
from ..models import AuditLog, NightRun, Setting, Station, User
from ..schemas import NightCreate
from ..services.algorithm import build_scenario, get_cfg, quick_compare, read_compare, run_night
from ..services.audit import audit
from bike_sched.config import fmt_hhmm
from bike_sched.demand import DemandModel

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/health")
def health():
    return {"status": "ok", "time": datetime.utcnow().isoformat()}


@router.get("/public-config")
def public_config(db: Session = Depends(get_db)):
    name = db.get(Setting, "system_name")
    reg = db.get(Setting, "self_registration")
    return {
        "system_name": name.value_json if name else "校园共享电单车调度系统",
        "self_registration": True if reg is None else bool(reg.value_json),
        "amap_key": AMAP_KEY,
        "amap_security": AMAP_SECURITY,
        "roles": ["admin", "operator", "viewer"],
    }


@router.get("/compare")
def compare(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = read_compare()
    if rows:
        return {"source": "experiments", "rows": rows}
    stations = db.query(Station).order_by(Station.id).all()
    return {"source": "live", "rows": quick_compare(stations)}


@router.get("/demand-profile")
def demand_profile(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    stations = db.query(Station).order_by(Station.id).all()
    if not stations:
        return {"times": [], "values": []}
    cfg = get_cfg()
    scenario = build_scenario(stations, cfg)
    dm = DemandModel(cfg, scenario)
    times = [fmt_hhmm(t) for t in dm.grid]
    values = [round(float(dm.true_demand(i).sum()), 2) for i in range(len(dm.grid))]
    return {"times": times, "values": values}


@router.get("/station-demand")
def station_demand(minute: int = Query(480, ge=0, le=1439),
                   horizon_min: int = Query(30, ge=10, le=120),
                   db: Session = Depends(get_db),
                   user: User = Depends(get_current_user)):
    """Read-only display data from the existing demand model, in rides/window.

    Partial time steps are weighted by overlap; parking bans are not demand nodes.
    No policy invocation, inventory mutation or database write is performed.
    """
    stations = [s for s in db.query(Station).order_by(Station.id).all()
                if s.func != "nopark"]
    if not stations:
        return {"items": [], "minute": minute, "horizon_min": horizon_min,
                "covered_min": 0, "source": "demand_model"}
    cfg = get_cfg()
    scenario = build_scenario(stations, cfg)
    dm = DemandModel(cfg, scenario)
    totals = [0.0] * len(stations)
    covered = 0
    for step, start in enumerate(dm.grid):
        overlap = max(0, min(start + dm.step_min, minute + horizon_min)
                      - max(start, minute))
        if not overlap:
            continue
        covered += overlap
        values = dm.true_demand(step)
        for i, value in enumerate(values):
            totals[i] += float(value) * overlap / dm.step_min
    return {
        "minute": minute, "horizon_min": horizon_min, "covered_min": covered,
        "source": "demand_model", "unit": "rides/window",
        "items": [{"station_id": s.id, "demand": round(totals[i], 3)}
                  for i, s in enumerate(stations)],
    }


@router.post("/night/solve")
def night_solve(payload: NightCreate, db: Session = Depends(get_db),
                user: User = Depends(get_current_user)):
    stations = db.query(Station).order_by(Station.id).all()
    if len(stations) < 3:
        raise HTTPException(status_code=400, detail="点位数不足")
    result = run_night(stations)
    run = NightRun(
        scenario_id=payload.scenario_id,
        status="done" if result.get("feasible") else "failed",
        result_json=result,
    )
    db.add(run)
    db.commit()
    db.refresh(run)
    audit(db, user, "night_solve", f"night:{run.id}",
          {"feasible": bool(result.get("feasible"))})
    return {"id": run.id, **result}


@router.get("/night")
def night_list(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(NightRun).order_by(NightRun.id.desc()).limit(10).all()
    return [
        {"id": r.id, "status": r.status,
         "created_at": r.created_at.isoformat() if r.created_at else None,
         "feasible": bool((r.result_json or {}).get("feasible"))}
        for r in rows
    ]


@router.get("/night/{night_id}")
def night_get(night_id: int, db: Session = Depends(get_db),
              user: User = Depends(get_current_user)):
    run = db.get(NightRun, night_id)
    if run is None:
        raise HTTPException(status_code=404, detail="记录不存在")
    return {"id": run.id, **(run.result_json or {})}


@router.get("/settings")
def get_settings(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Setting).all()
    return {r.key: r.value_json for r in rows}


@router.put("/settings")
def update_settings(payload: dict = Body(...), db: Session = Depends(get_db),
                    admin: User = Depends(require_roles("admin"))):
    for key, value in payload.items():
        row = db.get(Setting, key)
        if row is None:
            db.add(Setting(key=key, value_json=value))
        else:
            row.value_json = value
    db.commit()
    audit(db, admin, "update_settings", "", payload)
    return {"ok": True}


@router.get("/logs")
def logs(page: int = Query(1, ge=1), page_size: int = Query(20, ge=1, le=100),
         action: str | None = None,
         db: Session = Depends(get_db),
         admin: User = Depends(require_roles("admin"))):
    q = db.query(AuditLog)
    if action:
        q = q.filter(AuditLog.action == action)
    total = q.count()
    rows = (q.order_by(AuditLog.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all())
    return {
        "items": [
            {
                "id": r.id,
                "username": r.username,
                "action": r.action,
                "target": r.target,
                "detail": r.detail_json,
                "ip": r.ip,
                "created_at": r.created_at.isoformat() if r.created_at else None,
            }
            for r in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
