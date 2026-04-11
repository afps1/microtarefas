"""
Rota de setup inicial — criar primeiro admin geral.
Só funciona se não existir nenhum admin geral cadastrado.
Remover após uso.
"""
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Query
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from database import get_db
import models
import bcrypt
import os

router = APIRouter(prefix="/setup", tags=["setup"])


class SetupBody(BaseModel):
    name: str
    email: EmailStr
    password: str
    setup_key: str


@router.post("/upload-video")
async def upload_video(key: str = Query(...), file: UploadFile = File(...)):
    expected_key = os.getenv("SETUP_KEY")
    if not expected_key or key != expected_key:
        raise HTTPException(status_code=403, detail="key inválida")
    dest = f"/data/{file.filename}"
    content = await file.read()
    with open(dest, "wb") as f:
        f.write(content)
    return {"saved": dest, "size": len(content)}


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
