from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from database import get_db
import models

router = APIRouter(prefix="/cadastro", tags=["cadastro"])


class ResidentCreate(BaseModel):
    name: str
    phone: str
    apartment: str
    email: EmailStr | None = None
    condominium_id: int


class RunnerCreate(BaseModel):
    name: str
    phone: str
    email: EmailStr
    pix_key: str | None = None
    condominium_id: int


@router.get("/condominiums")
def list_condominiums_public(db: Session = Depends(get_db)):
    """Lista condomínios ativos — usado nos formulários de cadastro."""
    condos = db.query(models.Condominium).filter(models.Condominium.active == True).all()
    return [{"id": c.id, "name": c.name} for c in condos]


@router.get("/services/{condominium_id}")
def list_services_public(condominium_id: int, db: Session = Depends(get_db)):
    """Lista serviços ativos de um condomínio."""
    services = db.query(models.ServiceType).filter(
        models.ServiceType.condominium_id == condominium_id,
        models.ServiceType.active == True,
    ).all()
    return [{"id": s.id, "name": s.name, "price": s.price} for s in services]


@router.post("/morador", status_code=status.HTTP_201_CREATED)
def cadastrar_morador(body: ResidentCreate, db: Session = Depends(get_db)):
    condo = db.query(models.Condominium).filter(
        models.Condominium.id == body.condominium_id,
        models.Condominium.active == True,
    ).first()
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    existing = db.query(models.Resident).filter(models.Resident.phone == body.phone).first()
    if existing:
        raise HTTPException(status_code=409, detail="Telefone já cadastrado")

    resident = models.Resident(
        name=body.name,
        phone=body.phone,
        apartment=body.apartment,
        email=body.email,
        condominium_id=body.condominium_id,
    )
    db.add(resident)
    db.commit()
    db.refresh(resident)

    return {
        "id": resident.id,
        "name": resident.name,
        "message": "Cadastro realizado! Em breve você poderá usar o serviço via WhatsApp.",
    }


@router.post("/parceiro", status_code=status.HTTP_201_CREATED)
def cadastrar_parceiro(body: RunnerCreate, db: Session = Depends(get_db)):
    condo = db.query(models.Condominium).filter(
        models.Condominium.id == body.condominium_id,
        models.Condominium.active == True,
    ).first()
    if not condo:
        raise HTTPException(status_code=404, detail="Condomínio não encontrado")

    if db.query(models.Runner).filter(models.Runner.phone == body.phone).first():
        raise HTTPException(status_code=409, detail="Telefone já cadastrado")

    if db.query(models.Runner).filter(models.Runner.email == body.email).first():
        raise HTTPException(status_code=409, detail="E-mail já cadastrado")

    runner = models.Runner(
        name=body.name,
        phone=body.phone,
        email=body.email,
        pix_key=body.pix_key,
        condominium_id=body.condominium_id,
        status="pending",
    )
    db.add(runner)
    db.commit()
    db.refresh(runner)

    return {
        "id": runner.id,
        "name": runner.name,
        "message": "Cadastro recebido! Aguarde a aprovação do administrador do condomínio.",
    }
