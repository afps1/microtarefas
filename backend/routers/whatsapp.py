import os
import secrets
from datetime import datetime, timedelta, timezone
from fastapi import APIRouter, Request, Response, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from services.gpt_service import interpret_message
from services.whatsapp_service import send_message
import models

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
MAGIC_LINK_EXPIRY_MINUTES = int(os.getenv("MAGIC_LINK_EXPIRY_MINUTES", 10))
APP_URL = os.getenv("APP_URL", "http://localhost:3000")

def wa_phone(phone: str) -> str:
    """Garante que o número tenha o DDI 55 para envio via API da Meta."""
    return phone if phone.startswith("55") else f"55{phone}"


TASK_LABELS = {
    "lixo": "Levar lixo",
    "encomenda": "Buscar encomenda",
    "mercadinho": "Compra no mercadinho",
    "outro": "Tarefa avulsa",
}


# ── Verificação do webhook ──

@router.get("/webhook")
def verify_webhook(request: Request):
    params = dict(request.query_params)
    if (
        params.get("hub.mode") == "subscribe"
        and params.get("hub.verify_token") == VERIFY_TOKEN
    ):
        return Response(content=params["hub.challenge"], media_type="text/plain")
    raise HTTPException(status_code=403, detail="Token inválido")


# ── Recebimento de mensagens ──

@router.post("/webhook")
async def receive_webhook(request: Request, db: Session = Depends(get_db)):
    body = await request.json()

    try:
        entry = body["entry"][0]["changes"][0]["value"]
        messages = entry.get("messages")
        if not messages:
            return {"status": "no_message"}

        msg = messages[0]
        raw_phone = msg["from"]
        # WhatsApp envia com DDI (ex: 5511999999999), normaliza removendo o 55
        phone = raw_phone[2:] if raw_phone.startswith("55") and len(raw_phone) == 13 else raw_phone
        text = msg.get("text", {}).get("body", "").strip()

        if not text:
            return {"status": "ignored"}

    except (KeyError, IndexError):
        return {"status": "ignored"}

    import logging
    logging.getLogger(__name__).warning(f"[WEBHOOK] raw_phone={raw_phone} phone_normalizado={phone}")

    resident = db.query(models.Resident).filter(
        models.Resident.phone == phone,
        models.Resident.active == True,
    ).first()

    logging.getLogger(__name__).warning(f"[WEBHOOK] resident={resident}")

    if not resident:
        send_message(raw_phone, "Olá! Seu número não está cadastrado. Acesse o link para se cadastrar.")
        return {"status": "unregistered"}

    result = interpret_message(text)
    intent = result.get("intent")

    if intent == "solicitar_tarefa":
        await _handle_solicitar(resident, result, db)
    elif intent == "status":
        _handle_status(resident, db)
    elif intent == "cancelar":
        _handle_cancelar(resident, db)
    else:
        send_message(
            wa_phone(resident.phone),
            "Não entendi. Você pode pedir:\n• Levar lixo\n• Buscar encomenda\n• Compra no mercadinho",
        )

    return {"status": "ok"}


async def _handle_solicitar(resident: models.Resident, gpt_result: dict, db: Session):
    # Verifica se já tem tarefa aberta
    open_task = db.query(models.Task).filter(
        models.Task.resident_id == resident.id,
        models.Task.status.in_(["solicitado", "aceito", "em_execucao"]),
    ).first()

    if open_task:
        send_message(
            wa_phone(resident.phone),
            f"Você já tem uma tarefa em andamento: *{TASK_LABELS.get(open_task.type, open_task.type)}* ({open_task.status}). Aguarde a conclusão antes de solicitar uma nova.",
        )
        return

    task_type = gpt_result.get("task_type") or "outro"
    description = gpt_result.get("description")

    task = models.Task(
        condominium_id=resident.condominium_id,
        resident_id=resident.id,
        type=task_type,
        description=description,
        status="solicitado",
    )
    db.add(task)
    db.flush()

    label = TASK_LABELS.get(task_type, task_type)
    send_message(
        wa_phone(resident.phone),
        f"✅ Pedido recebido: *{label}*. Estamos buscando um parceiro disponível. Você será avisado em breve!",
    )

    db.commit()


def _handle_status(resident: models.Resident, db: Session):
    task = db.query(models.Task).filter(
        models.Task.resident_id == resident.id,
        models.Task.status.in_(["solicitado", "aceito", "em_execucao"]),
    ).order_by(models.Task.created_at.desc()).first()

    if not task:
        send_message(resident.phone, "Você não tem tarefas em andamento no momento.")
        return

    label = TASK_LABELS.get(task.type, task.type)
    status_pt = {
        "solicitado": "aguardando parceiro",
        "aceito": "parceiro a caminho",
        "em_execucao": "em execução",
    }.get(task.status, task.status)

    runner_info = f"\nParceiro: {task.runner.name}" if task.runner else ""
    send_message(resident.phone, f"📋 *{label}*\nStatus: {status_pt}{runner_info}")


def _handle_cancelar(resident: models.Resident, db: Session):
    task = db.query(models.Task).filter(
        models.Task.resident_id == resident.id,
        models.Task.status == "solicitado",
    ).order_by(models.Task.created_at.desc()).first()

    if not task:
        send_message(resident.phone, "Não há tarefa que possa ser cancelada agora.")
        return

    task.status = "recebido"
    task.updated_at = datetime.now(timezone.utc)
    db.commit()

    send_message(resident.phone, "Pedido cancelado com sucesso.")
