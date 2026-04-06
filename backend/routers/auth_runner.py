from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel, EmailStr
from datetime import datetime, timedelta, timezone
from database import get_db
from services.email_service import send_otp_email
from services.jwt_service import create_token
import models
import random
import string

router = APIRouter(prefix="/auth/runner", tags=["auth-runner"])

OTP_EXPIRY_MINUTES = 10


class RequestOtpBody(BaseModel):
    email: EmailStr


class VerifyOtpBody(BaseModel):
    email: EmailStr
    code: str


def _generate_otp() -> str:
    return "".join(random.choices(string.digits, k=6))


@router.post("/request-otp")
def request_otp(body: RequestOtpBody, db: Session = Depends(get_db)):
    runner = db.query(models.Runner).filter(models.Runner.email == body.email).first()
    if not runner:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="E-mail não cadastrado")
    if runner.status != "approved":
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Runner pendente de aprovação")

    code = _generate_otp()
    otp = models.OtpCode(
        email=body.email,
        code=code,
        expires_at=datetime.now(timezone.utc) + timedelta(minutes=OTP_EXPIRY_MINUTES),
    )
    db.add(otp)
    db.commit()

    send_otp_email(body.email, code)

    import os
    if os.getenv("EMAIL_MOCK", "true").lower() == "true":
        return {"message": "Código enviado para o e-mail", "dev_otp": code}

    return {"message": "Código enviado para o e-mail"}


@router.post("/verify-otp")
def verify_otp(body: VerifyOtpBody, db: Session = Depends(get_db)):
    otp = (
        db.query(models.OtpCode)
        .filter(
            models.OtpCode.email == body.email,
            models.OtpCode.code == body.code,
            models.OtpCode.used_at == None,
            models.OtpCode.expires_at > datetime.now(timezone.utc),
        )
        .order_by(models.OtpCode.created_at.desc())
        .first()
    )

    if not otp:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Código inválido ou expirado")

    otp.used_at = datetime.now(timezone.utc)
    db.commit()

    runner = db.query(models.Runner).filter(models.Runner.email == body.email).first()
    token = create_token(runner.id, "runner")

    from sqlalchemy import func
    avg = db.query(func.avg(models.Rating.score)).filter(models.Rating.runner_id == runner.id).scalar()
    rating = round(float(avg), 1) if avg else None

    return {
        "access_token": token,
        "token_type": "bearer",
        "runner": {
            "id": runner.id,
            "name": runner.name,
            "email": runner.email,
            "rating": rating,
        },
    }
