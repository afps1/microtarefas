from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from typing import Optional
from database import get_db
from dependencies import get_admin_condominio
import models
import pathlib

PHOTOS_DIR = pathlib.Path("/data/fotos")
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)

router = APIRouter(prefix="/admin/condominio", tags=["admin-condominio"])


def _condo_id(admin: models.AdminUser) -> int:
    if admin.role == "geral":
        raise HTTPException(status_code=400, detail="Admin geral deve usar os endpoints /admin/geral")
    return admin.condominium_id


class StatusUpdate(BaseModel):
    status: str


class ServiceTypeCreate(BaseModel):
    name: str
    description: Optional[str] = None
    price: int  # centavos


class ServiceTypeUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    price: Optional[int] = None
    active: Optional[bool] = None


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


# ── Serviços ──

@router.get("/services")
def list_services(db: Session = Depends(get_db), admin=Depends(get_admin_condominio)):
    condo_id = _condo_id(admin)
    services = db.query(models.ServiceType).filter(models.ServiceType.condominium_id == condo_id).all()
    return [
        {
            "id": s.id,
            "name": s.name,
            "description": s.description,
            "price": s.price,
            "price_fmt": f"R$ {s.price / 100:.2f}".replace(".", ",") if s.price else "a combinar",
            "active": s.active,
        }
        for s in services
    ]


@router.post("/services", status_code=status.HTTP_201_CREATED)
def create_service(body: ServiceTypeCreate, db: Session = Depends(get_db), admin=Depends(get_admin_condominio)):
    condo_id = _condo_id(admin)
    service = models.ServiceType(
        condominium_id=condo_id,
        name=body.name,
        description=body.description,
        price=body.price,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return {"id": service.id, "name": service.name, "price": service.price}


@router.patch("/services/{service_id}")
def update_service(service_id: int, body: ServiceTypeUpdate, db: Session = Depends(get_db), admin=Depends(get_admin_condominio)):
    condo_id = _condo_id(admin)
    service = db.query(models.ServiceType).filter(
        models.ServiceType.id == service_id,
        models.ServiceType.condominium_id == condo_id,
    ).first()
    if not service:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")

    if body.name is not None: service.name = body.name
    if body.description is not None: service.description = body.description
    if body.price is not None: service.price = body.price
    if body.active is not None: service.active = body.active

    db.commit()
    return {"id": service.id, "name": service.name, "price": service.price, "active": service.active}


@router.delete("/services/{service_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_service(service_id: int, db: Session = Depends(get_db), admin=Depends(get_admin_condominio)):
    condo_id = _condo_id(admin)
    service = db.query(models.ServiceType).filter(
        models.ServiceType.id == service_id,
        models.ServiceType.condominium_id == condo_id,
    ).first()
    if not service:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")
    db.delete(service)
    db.commit()


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
            "has_photo": bool(r.photo_url and pathlib.Path(r.photo_url).exists()),
        })
    return result


@router.post("/runners/{runner_id}/photo", status_code=status.HTTP_200_OK)
async def upload_runner_photo(
    runner_id: int,
    file: UploadFile = File(...),
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

    data = await file.read()
    if len(data) > 5 * 1024 * 1024:
        raise HTTPException(status_code=400, detail="Foto muito grande (máx 5MB)")

    path = PHOTOS_DIR / f"{runner_id}.jpg"
    path.write_bytes(data)
    runner.photo_url = str(path)
    db.commit()
    return {"status": "ok"}


@router.get("/runners/{runner_id}/photo")
def get_runner_photo(
    runner_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_condominio),
):
    condo_id = _condo_id(admin)
    runner = db.query(models.Runner).filter(
        models.Runner.id == runner_id,
        models.Runner.condominium_id == condo_id,
    ).first()
    if not runner or not runner.photo_url:
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    path = pathlib.Path(runner.photo_url)
    if not path.exists():
        raise HTTPException(status_code=404, detail="Foto não encontrada")
    return FileResponse(str(path), media_type="image/jpeg")


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
    result = []
    for t in tasks:
        rating = db.query(models.Rating).filter(models.Rating.task_id == t.id).first()
        result.append({
            "id": t.id,
            "type": t.type,
            "status": t.status,
            "resident_name": t.resident.name,
            "runner_name": t.runner.name if t.runner else None,
            "created_at": t.created_at,
            "rating": rating.score if rating else None,
        })
    return result


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


@router.get("/stats/tasks-by-service")
def stats_tasks_by_service(db: Session = Depends(get_db), admin=Depends(get_admin_condominio)):
    from datetime import date, timedelta
    from sqlalchemy import func
    condo_id = _condo_id(admin)
    since = date.today() - timedelta(days=30)
    rows = (
        db.query(models.Task.type, func.count(models.Task.id))
        .filter(
            models.Task.condominium_id == condo_id,
            models.Task.status == "recebido",
            models.Task.created_at >= since,
        )
        .group_by(models.Task.type)
        .order_by(func.count(models.Task.id).desc())
        .all()
    )
    return [{"label": r[0], "value": r[1]} for r in rows]


@router.get("/stats/tasks-by-runner")
def stats_tasks_by_runner(db: Session = Depends(get_db), admin=Depends(get_admin_condominio)):
    from datetime import date, timedelta
    from sqlalchemy import func
    condo_id = _condo_id(admin)
    since = date.today() - timedelta(days=30)
    rows = (
        db.query(models.Runner.name, func.count(models.Task.id))
        .join(models.Task, models.Task.runner_id == models.Runner.id)
        .filter(
            models.Task.condominium_id == condo_id,
            models.Task.status == "recebido",
            models.Task.created_at >= since,
        )
        .group_by(models.Runner.name)
        .order_by(func.count(models.Task.id).desc())
        .all()
    )
    return [{"label": r[0], "value": r[1]} for r in rows]
