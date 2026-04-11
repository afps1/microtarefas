"""
Rota de setup inicial — criar primeiro admin geral.
Só funciona se não existir nenhum admin geral cadastrado.
Remover após uso.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from database import get_db
import models
import bcrypt

router = APIRouter(prefix="/setup", tags=["setup"])


class SetupBody(BaseModel):
    name: str
    email: EmailStr
    password: str
    setup_key: str



@router.post("/admin-geral")
def create_first_admin(body: SetupBody, db: Session = Depends(get_db)):
    import os
    expected_key = os.getenv("SETUP_KEY")
    if not expected_key or body.setup_key != expected_key:
        raise HTTPException(status_code=403, detail="setup_key inválida")

    existing = db.query(models.AdminUser).filter(models.AdminUser.role == "geral").first()
    if existing:
        raise HTTPException(status_code=409, detail="Admin geral já existe")

    password_hash = bcrypt.hashpw(body.password.encode(), bcrypt.gensalt()).decode()
    admin = models.AdminUser(
        name=body.name,
        email=body.email,
        password_hash=password_hash,
        role="geral",
    )
    db.add(admin)
    db.commit()
    db.refresh(admin)
    return {"id": admin.id, "name": admin.name, "email": admin.email}
