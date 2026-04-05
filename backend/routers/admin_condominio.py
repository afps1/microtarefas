from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from dependencies import get_admin_condominio
import models

router = APIRouter(prefix="/admin/condominio", tags=["admin-condominio"])


def _condo_id(admin: models.AdminUser) -> int:
    """Retorna o condominium_id do admin. Admin geral deve passar ?condo_id explicitamente."""
    if admin.role == "geral":
        raise HTTPException(status_code=400, detail="Admin geral deve usar os endpoints /admin/geral")
    return admin.condominium_id


class StatusUpdate(BaseModel):
    status: str


# ── Parceiros ──

@router.get("/runners")
def list_runners(db: Session = Depends(get_db), admin=Depends(get_admin_condominio)):
    condo_id = _condo_id(admin)
    runners = db.query(models.Runner).filter(models.Runner.condominium_id == condo_id).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "email": r.email,
            "phone": r.phone,
            "pix_key": r.pix_key,
            "status": r.status,
        }
        for r in runners
    ]


@router.patch("/runners/{runner_id}/status")
def update_runner_status(
    runner_id: int,
    body: StatusUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_condominio),
):
    if body.status not in ("approved", "blocked", "pending"):
        raise HTTPException(status_code=400, detail="Status inválido")

    condo_id = _condo_id(admin)
    runner = db.query(models.Runner).filter(
        models.Runner.id == runner_id,
        models.Runner.condominium_id == condo_id,
    ).first()
    if not runner:
        raise HTTPException(status_code=404, detail="Parceiro não encontrado")

    runner.status = body.status
    db.commit()
    return {"id": runner.id, "status": runner.status}


# ── Moradores ──

@router.get("/residents")
def list_residents(db: Session = Depends(get_db), admin=Depends(get_admin_condominio)):
    condo_id = _condo_id(admin)
    residents = db.query(models.Resident).filter(models.Resident.condominium_id == condo_id).all()
    return [
        {
            "id": r.id,
            "name": r.name,
            "phone": r.phone,
            "apartment": r.apartment,
            "active": r.active,
        }
        for r in residents
    ]


@router.patch("/residents/{resident_id}/active")
def toggle_resident_active(
    resident_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_condominio),
):
    condo_id = _condo_id(admin)
    resident = db.query(models.Resident).filter(
        models.Resident.id == resident_id,
        models.Resident.condominium_id == condo_id,
    ).first()
    if not resident:
        raise HTTPException(status_code=404, detail="Morador não encontrado")

    resident.active = not resident.active
    db.commit()
    return {"id": resident.id, "active": resident.active}


# ── Tarefas ──

@router.get("/tasks")
def list_tasks(db: Session = Depends(get_db), admin=Depends(get_admin_condominio)):
    condo_id = _condo_id(admin)
    tasks = db.query(models.Task).filter(models.Task.condominium_id == condo_id).order_by(models.Task.created_at.desc()).all()
    return [
        {
            "id": t.id,
            "type": t.type,
            "status": t.status,
            "resident_name": t.resident.name,
            "runner_name": t.runner.name if t.runner else None,
            "created_at": t.created_at,
        }
        for t in tasks
    ]


# ── Stats ──

@router.get("/stats")
def stats(db: Session = Depends(get_db), admin=Depends(get_admin_condominio)):
    from datetime import date
    condo_id = _condo_id(admin)

    today = date.today()
    total_tasks_today = db.query(models.Task).filter(
        models.Task.condominium_id == condo_id,
        models.Task.created_at >= today,
    ).count()

    active_runners = db.query(models.Runner).filter(
        models.Runner.condominium_id == condo_id,
        models.Runner.status == "approved",
    ).count()

    residents = db.query(models.Resident).filter(
        models.Resident.condominium_id == condo_id,
        models.Resident.active == True,
    ).count()

    pending_runners = db.query(models.Runner).filter(
        models.Runner.condominium_id == condo_id,
        models.Runner.status == "pending",
    ).count()

    return {
        "total_tasks_today": total_tasks_today,
        "active_runners": active_runners,
        "residents": residents,
        "pending_runners": pending_runners,
    }
