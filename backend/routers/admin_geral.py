from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from database import get_db
from dependencies import get_admin_geral
import models
import bcrypt

router = APIRouter(prefix="/admin/geral", tags=["admin-geral"])


# ── Schemas ──

class CondominiumCreate(BaseModel):
    name: str
    address: str | None = None


class CondominiumUpdate(BaseModel):
    name: str | None = None
    address: str | None = None
    active: bool | None = None


class AdminCondominioCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    condominium_id: int


# ── Condomínios ──

@router.get("/condominiums")
def list_condominiums(db: Session = Depends(get_db), admin=Depends(get_admin_geral)):
    condominiums = db.query(models.Condominium).all()
    return [
        {
            "id": c.id,
            "name": c.name,
            "address": c.address,
            "active": c.active,
            "residents_count": len(c.residents),
            "runners_count": len(c.runners),
        }
        for c in condominiums
    ]


@router.post("/condominiums", status_code=status.HTTP_201_CREATED)
def create_condominium(
    body: CondominiumCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_geral),
):
    condo = models.Condominium(name=body.name, address=body.address)
    db.add(condo)
    db.commit()
    db.refresh(condo)
    return {"id": condo.id, "name": condo.name, "address": condo.address, "active": condo.active}


@router.patch("/condominiums/{condo_id}")
def update_condominium(
    condo_id: int,
    body: CondominiumUpdate,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_geral),
):
    condo = db.query(models.Condominium).filter(models.Condominium.id == condo_id).first()
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    if body.name is not None:
        condo.name = body.name
    if body.address is not None:
        condo.address = body.address
    if body.active is not None:
        condo.active = body.active

    db.commit()
    db.refresh(condo)
    return {"id": condo.id, "name": condo.name, "address": condo.address, "active": condo.active}


# ── Admins de condomínio ──

@router.get("/admins")
def list_admins(db: Session = Depends(get_db), admin=Depends(get_admin_geral)):
    admins = db.query(models.AdminUser).filter(models.AdminUser.role == "condominio").all()
    return [
        {
            "id": a.id,
            "name": a.name,
            "email": a.email,
            "active": a.active,
            "condominium_id": a.condominium_id,
            "condominium_name": a.condominium.name if a.condominium else None,
        }
        for a in admins
    ]


@router.post("/admins", status_code=status.HTTP_201_CREATED)
def create_admin_condominio(
    body: AdminCondominioCreate,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_geral),
):
    condo = db.query(models.Condominium).filter(models.Condominium.id == body.condominium_id).first()
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    existing = db.query(models.AdminUser).filter(models.AdminUser.email == body.email).first()
    if existing:
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")

    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    new_admin = models.AdminUser(
        name=body.name,
        email=body.email,
        password_hash=password_hash,
        role="condominio",
        condominium_id=body.condominium_id,
    )
    db.add(new_admin)
    db.commit()
    db.refresh(new_admin)

    return {
        "id": new_admin.id,
        "name": new_admin.name,
        "email": new_admin.email,
        "condominium_id": new_admin.condominium_id,
        "condominium_name": condo.name,
    }


@router.patch("/admins/{admin_id}/active")
def toggle_admin_active(
    admin_id: int,
    db: Session = Depends(get_db),
    admin=Depends(get_admin_geral),
):
    target = db.query(models.AdminUser).filter(
        models.AdminUser.id == admin_id,
        models.AdminUser.role == "condominio",
    ).first()
    if not target:
        raise HTTPException(status_code=404, detail="Admin não encontrado")

    target.active = not target.active
    db.commit()
    return {"id": target.id, "active": target.active}
