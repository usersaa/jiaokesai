from __future__ import annotations

import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from fastapi.responses import Response
from sqlalchemy.orm import Session

from ..core.database import get_db
from ..core.security import get_current_user, require_roles
from ..models import Station, User
from ..schemas import StationIn, StationOut
from ..services.audit import audit

router = APIRouter(prefix="/api/stations", tags=["stations"])


@router.get("", response_model=list[StationOut])
def list_stations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return db.query(Station).order_by(Station.id).all()


@router.post("", response_model=StationOut)
def create_station(payload: StationIn, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin", "operator"))):
    if db.get(Station, payload.id):
        raise HTTPException(status_code=400, detail="点位编号已存在")
    station = Station(**payload.model_dump())
    db.add(station)
    db.commit()
    db.refresh(station)
    audit(db, user, "create_station", station.id)
    return station


@router.put("/{station_id}", response_model=StationOut)
def update_station(station_id: str, payload: StationIn, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin", "operator"))):
    station = db.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="点位不存在")
    for key, value in payload.model_dump().items():
        setattr(station, key, value)
    db.commit()
    db.refresh(station)
    audit(db, user, "update_station", station.id)
    return station


@router.delete("/{station_id}")
def delete_station(station_id: str, db: Session = Depends(get_db),
                   user: User = Depends(require_roles("admin", "operator"))):
    station = db.get(Station, station_id)
    if station is None:
        raise HTTPException(status_code=404, detail="点位不存在")
    db.delete(station)
    db.commit()
    audit(db, user, "delete_station", station_id)
    return {"ok": True}


@router.post("/import")
async def import_stations(file: UploadFile = File(...), db: Session = Depends(get_db),
                          user: User = Depends(require_roles("admin", "operator"))):
    content = (await file.read()).decode("utf-8-sig")
    reader = csv.DictReader(io.StringIO(content))
    count = 0
    for row in reader:
        sid = str(row.get("id", "")).strip()
        if not sid:
            continue
        db.merge(Station(
            id=sid,
            name=str(row.get("name", "")).strip(),
            lng=float(row["lng"]),
            lat=float(row["lat"]),
            capacity=int(float(row.get("capacity", 30) or 30)),
            func=str(row.get("func", "other") or "other"),
            attraction=float(row.get("attraction", 0.5) or 0.5),
            init_bikes=int(float(row.get("init_bikes", 0) or 0)),
            target_bikes=float(row.get("target_bikes", 0) or 0),
        ))
        count += 1
    db.commit()
    audit(db, user, "import_stations", file.filename or "", {"count": count})
    return {"ok": True, "count": count}


@router.get("/export")
def export_stations(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = db.query(Station).order_by(Station.id).all()
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["id", "name", "lng", "lat", "capacity", "func",
                     "attraction", "init_bikes", "target_bikes"])
    for s in rows:
        writer.writerow([s.id, s.name, f"{s.lng:.6f}", f"{s.lat:.6f}",
                         s.capacity, s.func, f"{s.attraction:.3f}",
                         s.init_bikes, f"{s.target_bikes:.1f}"])
    return Response(
        content="\ufeff" + output.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": "attachment; filename=stations.csv"},
    )
