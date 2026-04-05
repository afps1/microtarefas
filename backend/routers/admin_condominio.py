from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from database import get_db
from dependencies import get_admin_condominio
import models

router = APIRouter(prefix="/admin/condominio", tags=["admin-condominio"])


def _condo_id(admin: models.AdminUser) -> int:
    if admin.role == "geral":
        raise HTTPException(status_code=400, detail="Admin geral deve usar os endpoints /admin/geral")
    return admin.condominium_id


class StatusUpdate(BaseModel):
    status: str


class RunnerUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[EmailStr] = None
    pix_key: Optional[str] = None


class ResidentUpdate(BaseModel):
    name: Optional[str] = None
    phone: Optional[str] = None
    apartment: Optional[str] = None
    email: Optional[EmailStr] = None


# ── Parceiros ──

@router.get("/runners")
def list_runners(db: Session = Depends(get_db), admin=Depends(get_admin_condominio)):
    condo_id = _condo_id(admin)
    from sqlalchemy import func
    runners = db.query(models.Runner).filter(models.Runner.condominium_id == condo_id).all()
    result = []
    for r in runners:
        avg = db.query(func.avg(models.Rating.score)).filter(models.Rating.runner_id == r.id).scalar()
        result.append({
            "id": r.id,
            "name": r.name,
            "email": r.email,
            "phone": r.phone,
            "pix_key": r.pix_key,
            "status": r.status,
            "rating": round(float(avg), 1) if avg else None,
        })
    return result


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


@router.patch("/runners/{runner_id}")
def update_runner(
    runner_id: int,
    body: RunnerUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_condominio),
):
    condo_id = _condo_id(admin)
    runner = db.query(models.Runner).filter(
        models.Runner.id == runner_id,
        models.Runner.condominium_id == condo_id,
    ).first()
    if not runner:
        raise HTTPException(status_code=404, detail="Parceiro não encontrado")

    if body.name is not None: runner.name = body.name
    if body.phone is not None: runner.phone = body.phone
    if body.email is not None: runner.email = body.email
    if body.pix_key is not None: runner.pix_key = body.pix_key

    db.commit()
    return {"id": runner.id, "name": runner.name, "email": runner.email, "phone": runner.phone, "pix_key": runner.pix_key}


@router.delete("/runners/{runner_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_runner(
    runner_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_condominio),
):
    condo_id = _condo_id(admin)
    runner = db.query(models.Runner).filter(
        models.Runner.id == runner_id,
        models.Runner.condominium_id == condo_id,
    ).first()
    if not runner:
        raise HTTPException(status_code=404, detail="Parceiro não encontrado")
    db.delete(runner)
    db.commit()


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


@router.patch("/residents/{resident_id}")
def update_resident(
    resident_id: int,
    body: ResidentUpdate,
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

    if body.name is not None: resident.name = body.name
    if body.phone is not None: resident.phone = body.phone
    if body.apartment is not None: resident.apartment = body.apartment
    if body.email is not None: resident.email = body.email

    db.commit()
    return {"id": resident.id, "name": resident.name, "phone": resident.phone, "apartment": resident.apartment}


@router.delete("/residents/{resident_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_resident(
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
    db.delete(resident)
    db.commit()


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
