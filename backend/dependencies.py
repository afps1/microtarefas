from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from database import get_db
from services.jwt_service import decode_token
import models

bearer = HTTPBearer()


def get_current_runner(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> models.Runner:
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    if payload.get("type") != "runner":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")

    runner = db.query(models.Runner).filter(models.Runner.id == int(payload["sub"])).first()
    if not runner or runner.status != "approved":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Parceiro não autorizado")

    return runner


def _get_admin(credentials: HTTPAuthorizationCredentials, db: Session) -> models.AdminUser:
    try:
        payload = decode_token(credentials.credentials)
    except Exception:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Token inválido")

    if payload.get("type") != "admin":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")

    admin = db.query(models.AdminUser).filter(models.AdminUser.id == int(payload["sub"])).first()
    if not admin or not admin.active:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin não autorizado")

    return admin


def get_current_admin(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> models.AdminUser:
    """Qualquer admin autenticado (geral ou condomínio)."""
    return _get_admin(credentials, db)


def get_admin_geral(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> models.AdminUser:
    """Somente admin geral (da empresa)."""
    admin = _get_admin(credentials, db)
    if admin.role != "geral":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Restrito ao admin geral")
    return admin


def get_admin_condominio(
    credentials: HTTPAuthorizationCredentials = Depends(bearer),
    db: Session = Depends(get_db),
) -> models.AdminUser:
    """Admin de condomínio ou admin geral (acesso amplo)."""
    admin = _get_admin(credentials, db)
    if admin.role not in ("geral", "condominio"):
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Acesso negado")
    return admin
