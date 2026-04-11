import os
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Request, Response, Depends, HTTPException
from sqlalchemy.orm import Session
from database import get_db
from services.gpt_service import interpret_message
from services.whatsapp_service import send_message, get_media_download_url
from services.push_service import send_push
import models

router = APIRouter(prefix="/whatsapp", tags=["whatsapp"])
log = logging.getLogger(__name__)

VERIFY_TOKEN = os.getenv("VERIFY_TOKEN", "")
APP_URL = os.getenv("APP_URL", "http://localhost:3000")


def wa_phone(phone: str) -> str:
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
        phone = raw_phone[2:] if raw_phone.startswith("55") and len(raw_phone) == 13 else raw_phone
        msg_type = msg.get("type", "text")
        text = ""
        media_id = None

        if msg_type == "text":
            text = msg.get("text", {}).get("body", "").strip()
            if not text:
                return {"status": "ignored"}
        elif msg_type == "image":
            media_id = msg.get("image", {}).get("id")
            if not media_id:
                return {"status": "ignored"}
        else:
            return {"status": "ignored"}

    except (KeyError, IndexError):
        return {"status": "ignored"}

    log.warning(f"[WEBHOOK] raw_phone={raw_phone} phone_normalizado={phone}")

    resident = db.query(models.Resident).filter(
        models.Resident.phone == phone,
        models.Resident.active == True,
    ).first()

    log.warning(f"[WEBHOOK] resident={resident}")

    if not resident:
        contact_email = os.getenv("CONTACT_EMAIL", "")
        contato = f"\n\nCaso tenha interesse em conhecer o Postino, entre em contato com {contact_email}" if contact_email else ""
        send_message(raw_phone, f"Olá! Seu número não está cadastrado no sistema. Entre em contato com o responsável pelo seu local para ter acesso ao Postino. 😊{contato}")
        return {"status": "unregistered"}

    text_lower = text.lower().strip() if text else ""

    # 1. Aguardando confirmação de pedido
    pending = db.query(models.PendingRequest).filter(
        models.PendingRequest.resident_id == resident.id
    ).first()

    if pending:
        if pending.awaiting_observation:
            # Qualquer texto vira observação; "não" pula
            obs = None if text_lower in ("não", "nao", "n", "nao obrigado", "não obrigado") else text
            pending.description = obs
            pending.awaiting_observation = False
            db.commit()
            await _confirmar_pedido(resident, pending, db)
        elif text_lower in ("sim", "s", "confirmar", "confirma", "ok"):
            pending.awaiting_observation = True
            db.commit()
            send_message(
                wa_phone(resident.phone),
                "Tem alguma observação para o parceiro? Responda com o texto ou *não* para pular.",
            )
        elif text_lower in ("não", "nao", "n", "cancelar", "cancela"):
            db.delete(pending)
            db.commit()
            send_message(wa_phone(resident.phone), "Pedido cancelado. Quando quiser, é só pedir!")
        else:
            service = pending.service_type
            price_info = (" — preço sugerido *R$ {:.2f}*".format(service.price / 100).replace(".", ",") if service.price else " — preço *a combinar*") if service else ""
            label = service.name if service else TASK_LABELS.get(pending.task_type, pending.task_type)
            send_message(
                wa_phone(resident.phone),
                f"Responda *sim* para confirmar ou *não* para cancelar.\n\n_{label}{price_info}_",
            )
        return {"status": "ok"}

    # 2. Chat durante em_execucao
    active_task = db.query(models.Task).filter(
        models.Task.resident_id == resident.id,
        models.Task.status == "em_execucao",
    ).first()

    if active_task:
        if msg_type == "text":
            db.add(models.TaskMessage(
                task_id=active_task.id,
                sender="morador",
                type="text",
                content=text,
            ))
        elif msg_type == "image" and media_id:
            db.add(models.TaskMessage(
                task_id=active_task.id,
                sender="morador",
                type="image",
                content=media_id,
            ))
        db.commit()
        return {"status": "ok"}

    # 3. Avaliação pendente (resposta 1-5)
    if text_lower in ("1", "2", "3", "4", "5"):
        if _handle_avaliacao(resident, int(text_lower), db):
            return {"status": "ok"}

    # 3. Interpreta intenção
    services = db.query(models.ServiceType).filter(
        models.ServiceType.condominium_id == resident.condominium_id,
        models.ServiceType.active == True,
    ).all()
    service_names = [s.name for s in services]
    result = interpret_message(text, services=service_names)
    intent = result.get("intent")

    if intent == "solicitar_tarefa":
        task_type = result.get("task_type")
        if task_type == "outro":
            _handle_servico_indisponivel(resident, services, db)
        else:
            _handle_solicitar(resident, result, db)
    elif intent == "listar_servicos":
        _handle_listar_servicos(resident, services, db)
    elif intent == "status":
        _handle_status(resident, db)
    elif intent == "cancelar":
        _handle_cancelar(resident, db)
    else:
        _handle_outro(resident, services, db)

    return {"status": "ok"}


def _handle_solicitar(resident: models.Resident, gpt_result: dict, db: Session):
    # Verifica se já tem tarefa aberta
    open_task = db.query(models.Task).filter(
        models.Task.resident_id == resident.id,
        models.Task.status.in_(["solicitado", "aceito", "em_execucao"]),
    ).first()

    if open_task:
        label = TASK_LABELS.get(open_task.type, open_task.type)
        send_message(
            wa_phone(resident.phone),
            f"Você já tem uma tarefa em andamento: *{label}* ({open_task.status}). Aguarde a conclusão antes de solicitar uma nova.",
        )
        return

    task_type = gpt_result.get("task_type") or "outro"
    description = gpt_result.get("description")

    # Busca serviço pelo nome exato retornado pelo GPT
    service = db.query(models.ServiceType).filter(
        models.ServiceType.condominium_id == resident.condominium_id,
        models.ServiceType.active == True,
        models.ServiceType.name == task_type,
    ).first()

    # Fallback: busca por similaridade
    if not service and task_type != "outro":
        service = db.query(models.ServiceType).filter(
            models.ServiceType.condominium_id == resident.condominium_id,
            models.ServiceType.active == True,
            models.ServiceType.name.ilike(f"%{task_type}%"),
        ).first()

    label = service.name if service else task_type
    price_info = (" — preço sugerido *R$ {:.2f}*".format(service.price / 100).replace(".", ",") if service.price else " — preço *a combinar*") if service else ""

    # Salva pedido pendente aguardando confirmação
    existing = db.query(models.PendingRequest).filter(
        models.PendingRequest.resident_id == resident.id
    ).first()
    if existing:
        db.delete(existing)

    pending = models.PendingRequest(
        resident_id=resident.id,
        task_type=task_type,
        service_type_id=service.id if service else None,
        description=description,
    )
    db.add(pending)
    db.commit()

    send_message(
        wa_phone(resident.phone),
        f"Você quer solicitar: *{label}*{price_info}\n\nConfirma? Responda *sim* ou *não*.",
    )


async def _confirmar_pedido(resident: models.Resident, pending: models.PendingRequest, db: Session):
    service = pending.service_type
    task = models.Task(
        condominium_id=resident.condominium_id,
        resident_id=resident.id,
        type=pending.task_type,
        description=pending.description,
        status="solicitado",
        service_type_id=service.id if service else None,
        price=service.price if service else None,
    )
    db.add(task)
    db.delete(pending)
    db.flush()

    label = service.name if service else TASK_LABELS.get(pending.task_type, pending.task_type)
    price_info = (" — preço sugerido *R$ {:.2f}*".format(service.price / 100).replace(".", ",") if service.price else " — preço *a combinar*") if service else ""
    send_message(
        wa_phone(resident.phone),
        f"✅ Pedido confirmado: *{label}*{price_info}. Estamos buscando um parceiro disponível. Você será avisado em breve!\n\nSe quiser cancelar, é só responder *cancelar*.",
    )
    db.commit()

    # Notifica parceiros aprovados do condomínio via push
    subs = (
        db.query(models.PushSubscription)
        .join(models.Runner, models.Runner.id == models.PushSubscription.runner_id)
        .filter(
            models.Runner.condominium_id == resident.condominium_id,
            models.Runner.status == "approved",
            models.Runner.available == True,
        )
        .all()
    )
    for sub in subs:
        send_push(
            {"endpoint": sub.endpoint, "keys": {"p256dh": sub.p256dh, "auth": sub.auth}},
            title="Nova tarefa!",
            body=f"{label} — {resident.apartment}",
        )


def _handle_status(resident: models.Resident, db: Session):
    task = db.query(models.Task).filter(
        models.Task.resident_id == resident.id,
        models.Task.status.in_(["solicitado", "aceito", "em_execucao"]),
    ).order_by(models.Task.created_at.desc()).first()

    if not task:
        send_message(wa_phone(resident.phone), "Você não tem tarefas em andamento no momento.")
        return

    label = TASK_LABELS.get(task.type, task.type)
    status_pt = {
        "solicitado": "aguardando parceiro",
        "aceito": "parceiro a caminho",
        "em_execucao": "em execução",
    }.get(task.status, task.status)

    runner_info = f"\nParceiro: {task.runner.name}" if task.runner else ""
    send_message(wa_phone(resident.phone), f"📋 *{label}*\nStatus: {status_pt}{runner_info}")


def _handle_cancelar(resident: models.Resident, db: Session):
    # Cancela pedido pendente primeiro
    pending = db.query(models.PendingRequest).filter(
        models.PendingRequest.resident_id == resident.id
    ).first()
    if pending:
        db.delete(pending)
        db.commit()
        send_message(wa_phone(resident.phone), "Pedido cancelado.")
        return

    task = db.query(models.Task).filter(
        models.Task.resident_id == resident.id,
        models.Task.status == "solicitado",
    ).order_by(models.Task.created_at.desc()).first()

    if not task:
        send_message(wa_phone(resident.phone), "Não há tarefa que possa ser cancelada agora.")
        return

    task.status = "cancelado"
    task.updated_at = datetime.now(timezone.utc)
    db.commit()
    send_message(wa_phone(resident.phone), "Pedido cancelado com sucesso.")


def _menu_servicos(services) -> str:
    if services:
        return "\n".join([f"• {s.name} — {'R$ ' + '{:.2f}'.format(s.price / 100).replace('.', ',') if s.price else 'a combinar'}" for s in services])
    return "• Nenhum serviço disponível no momento."


def _handle_listar_servicos(resident: models.Resident, services, db: Session):
    menu = _menu_servicos(services)
    send_message(
        wa_phone(resident.phone),
        f"Estes são os serviços disponíveis:\n\n{menu}\n\nÉ só pedir!",
    )


def _handle_servico_indisponivel(resident: models.Resident, services, db: Session):
    menu = _menu_servicos(services)
    admin_contact = db.query(models.AdminUser).filter(
        models.AdminUser.condominium_id == resident.condominium_id,
        models.AdminUser.role == "condominio",
        models.AdminUser.active == True,
    ).first()
    contato = f"\n\nPara solicitar novos serviços, entre em contato com *{admin_contact.name}* pelo e-mail {admin_contact.email}." if admin_contact else ""
    send_message(
        wa_phone(resident.phone),
        f"Esse serviço não está disponível. Mas você pode solicitar:\n\n{menu}{contato}",
    )


def _handle_outro(resident: models.Resident, services, db: Session):
    menu = _menu_servicos(services)
    send_message(
        wa_phone(resident.phone),
        f"Olá! Posso ajudar a solicitar serviços:\n\n{menu}\n\nÉ só me dizer o que precisa!",
    )


def _handle_avaliacao(resident: models.Resident, score: int, db) -> bool:
    task = (
        db.query(models.Task)
        .filter(
            models.Task.resident_id == resident.id,
            models.Task.status == "recebido",
            models.Task.runner_id != None,
        )
        .outerjoin(models.Rating, models.Rating.task_id == models.Task.id)
        .filter(models.Rating.id == None)
        .order_by(models.Task.updated_at.desc())
        .first()
    )

    if not task:
        return False

    rating = models.Rating(
        task_id=task.id,
        runner_id=task.runner_id,
        resident_id=resident.id,
        score=score,
    )
    db.add(rating)
    db.commit()

    estrelas = "⭐" * score
    send_message(wa_phone(resident.phone), f"Obrigado pela avaliação! {estrelas}")
    return True
