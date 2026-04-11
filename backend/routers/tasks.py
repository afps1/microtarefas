from fastapi import APIRouter, Depends, HTTPException, status, UploadFile, File, Query
from fastapi.responses import Response
from sqlalchemy import false as sql_false
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone
from database import get_db
from dependencies import get_current_runner
from services.whatsapp_service import send_message, send_image, upload_media, get_media_download_url, download_media_bytes
from services.jwt_service import decode_token
import models
import pathlib
import os

PHOTOS_DIR = pathlib.Path("/data/fotos")
PHOTOS_DIR.mkdir(parents=True, exist_ok=True)


def wa_phone(phone: str) -> str:
    return phone if phone.startswith("55") else f"55{phone}"


def _msg_concluido(runner, task, db):
    # Busca preço: snapshot da tarefa ou serviço atual
    price = task.price
    if not price and task.service_type_id:
        service = db.query(models.ServiceType).filter(models.ServiceType.id == task.service_type_id).first()
        if service:
            price = service.price
    if not price:
        # Tenta pelo tipo da tarefa
        service = db.query(models.ServiceType).filter(
            models.ServiceType.condominium_id == task.condominium_id,
            models.ServiceType.active == True,
        ).first()
        if service:
            price = service.price

    price_str = (f"💸 Valor sugerido: *R$ {price / 100:.2f}*\n".replace(".", ",") if price else "💸 Valor: *a combinar*\n")
    return (
        f"🎉 Tarefa concluída por *{runner.name}*!\n\n"
        f"{price_str}"
        f"Chave Pix: *{runner.pix_key or 'não cadastrada'}*\n\n"
        f"Você paga direto ao parceiro via Pix."
    )

router = APIRouter(prefix="/tasks", tags=["tasks"])

VALID_TRANSITIONS = {
    "solicitado": "aceito",
    "aceito": "em_execucao",
    "em_execucao": "concluido",
    "concluido": "recebido",
}


class StatusUpdate(BaseModel):
    status: str


@router.get("/my")
def my_tasks(db: Session = Depends(get_db), runner=Depends(get_current_runner)):
    """Retorna tarefas do condomínio do parceiro — pendentes (filtradas por serviços aceitos) + as suas em andamento."""
    active_service_ids = [
        rs.service_type_id
        for rs in db.query(models.RunnerService).filter(models.RunnerService.runner_id == runner.id).all()
    ]

    tasks = (
        db.query(models.Task)
        .filter(
            models.Task.condominium_id == runner.condominium_id,
            models.Task.status.in_(["solicitado", "aceito", "em_execucao", "concluido"]),
        )
        .filter(
            # Próprias tarefas em andamento sempre visíveis; solicitadas só se o serviço está ativo
            (models.Task.runner_id == runner.id) |
            (
                (models.Task.runner_id == None) &
                (models.Task.service_type_id.in_(active_service_ids) if active_service_ids else sql_false())
            )
        )
        .order_by(models.Task.created_at.desc())
        .all()
    )

    return [
        {
            "id": t.id,
            "type": t.type,
            "description": t.description,
            "status": t.status,
            "resident_name": t.resident.name,
            "resident_apartment": t.resident.apartment,
            "created_at": t.created_at,
            "is_mine": t.runner_id == runner.id,
        }
        for t in tasks
    ]


@router.patch("/{task_id}/status")
def update_task_status(
    task_id: int,
    body: StatusUpdate,
    db: Session = Depends(get_db),
    runner=Depends(get_current_runner),
):
    task = db.query(models.Task).filter(
        models.Task.id == task_id,
        models.Task.condominium_id == runner.condominium_id,
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")

    expected_next = VALID_TRANSITIONS.get(task.status)

    if body.status != expected_next:
        raise HTTPException(
            status_code=400,
            detail=f"Transição inválida: {task.status} → {body.status}",
        )

    # Ao aceitar: reserva a tarefa para este parceiro (transacional)
    if body.status == "aceito":
        if task.runner_id is not None and task.runner_id != runner.id:
            raise HTTPException(status_code=409, detail="Tarefa já foi aceita por outro parceiro")
        # Bloqueia aceitar nova tarefa se já tem uma ativa
        active = db.query(models.Task).filter(
            models.Task.runner_id == runner.id,
            models.Task.status.in_(["aceito", "em_execucao"]),
        ).first()
        if active:
            raise HTTPException(status_code=409, detail="Você já tem uma tarefa em andamento")
        task.runner_id = runner.id

    # Garante que só quem aceitou pode avançar
    if task.runner_id and task.runner_id != runner.id:
        raise HTTPException(status_code=403, detail="Esta tarefa pertence a outro parceiro")

    task.status = body.status
    task.updated_at = datetime.now(timezone.utc)
    db.commit()

    # Notifica morador via WhatsApp
    NOTIFICACOES = {
        "aceito": lambda r, t, _db: f"✅ *{r.name}* aceitou sua tarefa e está a caminho!",
        "em_execucao": lambda r, t, _db: f"🏃 *{r.name}* está executando sua tarefa agora.\n\nSe precisar, pode mandar uma mensagem aqui mesmo — o parceiro receberá em tempo real.",
        "concluido": lambda r, t, _db: _msg_concluido(r, t, _db),
        "recebido": lambda r, t, _db: f"Como você avalia o serviço de *{r.name}*?\n\nResponda com um número de 1 a 5:\n⭐ 1 - Ruim\n⭐⭐ 2 - Regular\n⭐⭐⭐ 3 - Bom\n⭐⭐⭐⭐ 4 - Ótimo\n⭐⭐⭐⭐⭐ 5 - Excelente",
    }
    msg_fn = NOTIFICACOES.get(body.status)
    if msg_fn:
        try:
            phone = wa_phone(task.resident.phone)
            send_message(phone, msg_fn(runner, task, db))
            # Ao aceitar: envia foto do parceiro se disponível
            if body.status == "aceito" and runner.photo_url:
                photo_path = pathlib.Path(runner.photo_url)
                if photo_path.exists():
                    photo_bytes = photo_path.read_bytes()
                    media_id = upload_media(photo_bytes, "image/jpeg", "parceiro.jpg")
                    if media_id:
                        send_image(phone, media_id)
        except Exception as e:
            import logging
            logging.getLogger(__name__).error(f"Erro ao notificar morador: {e}")

    return {"id": task.id, "status": task.status}


# ── Chat ──

class TextMessage(BaseModel):
    content: str


@router.get("/{task_id}/messages")
def get_messages(task_id: int, db: Session = Depends(get_db), runner=Depends(get_current_runner)):
    task = db.query(models.Task).filter(
        models.Task.id == task_id,
        models.Task.condominium_id == runner.condominium_id,
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")

    messages = db.query(models.TaskMessage).filter(
        models.TaskMessage.task_id == task_id,
    ).order_by(models.TaskMessage.created_at.asc()).all()

    return [
        {
            "id": m.id,
            "sender": m.sender,
            "type": m.type,
            "content": m.content,
            "created_at": m.created_at,
        }
        for m in messages
    ]


@router.post("/{task_id}/message")
def send_text(task_id: int, body: TextMessage, db: Session = Depends(get_db), runner=Depends(get_current_runner)):
    task = db.query(models.Task).filter(
        models.Task.id == task_id,
        models.Task.runner_id == runner.id,
        models.Task.status == "em_execucao",
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada ou não em execução")

    db.add(models.TaskMessage(task_id=task_id, sender="parceiro", type="text", content=body.content))
    db.commit()
    send_message(wa_phone(task.resident.phone), body.content)
    return {"status": "ok"}


@router.post("/{task_id}/message/media")
async def send_media(task_id: int, file: UploadFile = File(...), db: Session = Depends(get_db), runner=Depends(get_current_runner)):
    task = db.query(models.Task).filter(
        models.Task.id == task_id,
        models.Task.runner_id == runner.id,
        models.Task.status == "em_execucao",
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada ou não em execução")

    file_bytes = await file.read()
    mime_type = file.content_type or "image/jpeg"
    media_id = upload_media(file_bytes, mime_type, file.filename or "foto.jpg")
    if not media_id:
        raise HTTPException(status_code=502, detail="Erro ao fazer upload da imagem")

    db.add(models.TaskMessage(task_id=task_id, sender="parceiro", type="image", content=media_id))
    db.commit()
    send_image(wa_phone(task.resident.phone), media_id)
    return {"status": "ok", "media_id": media_id}


class PixPayload(BaseModel):
    payload: str


@router.post("/{task_id}/pix")
def send_pix_code(task_id: int, body: PixPayload, db: Session = Depends(get_db), runner=Depends(get_current_runner)):
    task = db.query(models.Task).filter(
        models.Task.id == task_id,
        models.Task.runner_id == runner.id,
        models.Task.status == "em_execucao",
    ).first()
    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada ou não em execução")

    msg_text = f"Código Pix:\n{body.payload}"
    db.add(models.TaskMessage(task_id=task_id, sender="parceiro", type="text", content=msg_text))
    db.commit()

    phone = wa_phone(task.resident.phone)
    send_message(phone, "💸 Código Pix para pagamento — copie a linha abaixo:")
    send_message(phone, body.payload)
    return {"status": "ok"}


@router.get("/media/{media_id}")
def proxy_media(media_id: str, token: str = Query(...)):
    payload = decode_token(token)
    if not payload:
        raise HTTPException(status_code=401, detail="Token inválido")

    url, mime_type = get_media_download_url(media_id)
    if not url:
        raise HTTPException(status_code=404, detail="Mídia não encontrada")

    data = download_media_bytes(url)
    if not data:
        raise HTTPException(status_code=502, detail="Erro ao baixar mídia")

    return Response(content=data, media_type=mime_type or "image/jpeg")



@router.get("/push-vapid-key")
def get_vapid_key():
    return {"public_key": os.getenv("VAPID_PUBLIC_KEY", "")}


class PushSubscriptionBody(BaseModel):
    endpoint: str
    keys: dict


class AvailableUpdate(BaseModel):
    available: bool


@router.patch("/me/available")
def set_available(body: AvailableUpdate, db: Session = Depends(get_db), runner=Depends(get_current_runner)):
    runner.available = body.available
    db.commit()
    return {"available": runner.available}


@router.post("/me/push-subscription")
def save_push_subscription(body: PushSubscriptionBody, db: Session = Depends(get_db), runner=Depends(get_current_runner)):
    existing = db.query(models.PushSubscription).filter(models.PushSubscription.runner_id == runner.id).first()
    if existing:
        existing.endpoint = body.endpoint
        existing.p256dh = body.keys.get("p256dh", "")
        existing.auth = body.keys.get("auth", "")
    else:
        db.add(models.PushSubscription(
            runner_id=runner.id,
            endpoint=body.endpoint,
            p256dh=body.keys.get("p256dh", ""),
            auth=body.keys.get("auth", ""),
        ))
    db.commit()
    return {"status": "ok"}


@router.get("/me/services")
def get_my_services(db: Session = Depends(get_db), runner=Depends(get_current_runner)):
    """Retorna todos os serviços do condomínio com flag de se o parceiro os aceita."""
    services = db.query(models.ServiceType).filter(
        models.ServiceType.condominium_id == runner.condominium_id,
        models.ServiceType.active == True,
    ).all()

    active_ids = {
        rs.service_type_id
        for rs in db.query(models.RunnerService).filter(models.RunnerService.runner_id == runner.id).all()
    }

    return [
        {
            "id": s.id,
            "name": s.name,
            "price": s.price,
            "price_fmt": f"R$ {s.price / 100:.2f}".replace(".", ",") if s.price else "a combinar",
            "active": s.id in active_ids,
        }
        for s in services
    ]


class ServiceToggle(BaseModel):
    service_type_id: int
    active: bool


@router.patch("/me/services")
def toggle_my_service(body: ServiceToggle, db: Session = Depends(get_db), runner=Depends(get_current_runner)):
    """Ativa ou desativa um serviço para o parceiro."""
    service = db.query(models.ServiceType).filter(
        models.ServiceType.id == body.service_type_id,
        models.ServiceType.condominium_id == runner.condominium_id,
    ).first()
    if not service:
        raise HTTPException(status_code=404, detail="Serviço não encontrado")

    existing = db.query(models.RunnerService).filter(
        models.RunnerService.runner_id == runner.id,
        models.RunnerService.service_type_id == body.service_type_id,
    ).first()

    if body.active and not existing:
        db.add(models.RunnerService(runner_id=runner.id, service_type_id=body.service_type_id))
        db.commit()
    elif not body.active and existing:
        db.delete(existing)
        db.commit()

    return {"service_type_id": body.service_type_id, "active": body.active}


@router.post("/{task_id}/cancel")
def cancel_task(
    task_id: int,
    db: Session = Depends(get_db),
    runner=Depends(get_current_runner),
):
    task = db.query(models.Task).filter(
        models.Task.id == task_id,
        models.Task.condominium_id == runner.condominium_id,
        models.Task.runner_id == runner.id,
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")

    if task.status not in ("aceito", "em_execucao"):
        raise HTTPException(status_code=400, detail="Tarefa não pode ser cancelada neste status")

    task.status = "solicitado"
    task.runner_id = None
    task.updated_at = datetime.now(timezone.utc)
    db.commit()

    try:
        send_message(
            wa_phone(task.resident.phone),
            f"⚠️ O parceiro precisou cancelar sua tarefa. Estamos buscando outro parceiro disponível.\n\nSe quiser cancelar, é só responder *cancelar*.",
        )
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Erro ao notificar morador: {e}")

    return {"id": task.id, "status": task.status}
