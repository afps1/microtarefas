"""
Endpoint público de link mágico para parceiros.
GET  /t/{token}  → aceita tarefa atomicamente e retorna página HTML
PATCH /t/{token}/status → avança status da tarefa
GET  /t/{token}/messages → mensagens do chat
POST /t/{token}/message  → envia mensagem ao solicitante
"""
import pathlib
import logging
from datetime import datetime, timezone
from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse
from sqlalchemy import update as sql_update
from sqlalchemy.orm import Session
from pydantic import BaseModel
from database import get_db
from services.whatsapp_service import send_message, send_image, upload_media, download_media_bytes, get_media_download_url
import models

router = APIRouter(prefix="/t", tags=["tarefa"])
log = logging.getLogger(__name__)

VALID_TRANSITIONS = {
    "aceito": "em_execucao",
    "em_execucao": "concluido",
    "concluido": "recebido",
}

TASK_LABELS = {
    "lixo": "Levar lixo",
    "encomenda": "Buscar encomenda",
    "mercadinho": "Compra no mercadinho",
    "outro": "Tarefa avulsa",
}


def wa_phone(phone: str) -> str:
    return phone if phone.startswith("55") else f"55{phone}"


def _get_link(token: str, db: Session):
    now = datetime.now(timezone.utc)
    link = db.query(models.MagicLink).filter(models.MagicLink.token == token).first()
    if not link:
        raise HTTPException(status_code=404, detail="Link não encontrado")
    if link.expires_at.replace(tzinfo=timezone.utc) < now:
        raise HTTPException(status_code=410, detail="Link expirado")
    return link


def _msg_concluido(runner, task, db):
    price = task.price
    if price is None and task.service_type_id:
        service = db.query(models.ServiceType).filter(models.ServiceType.id == task.service_type_id).first()
        if service:
            price = service.price
    price_str = f"Valor sugerido: *R$ {price / 100:.2f}*\n".replace(".", ",") if price else "Valor: *a combinar*\n"
    return (
        f"Tarefa concluída por *{runner.name}*!\n\n"
        f"{price_str}"
        f"Chave Pix: *{runner.pix_key or 'não cadastrada'}*\n\n"
        f"Você paga direto ao parceiro via Pix."
    )


def _render_page(token: str, runner: models.Runner, task: models.Task, db: Session) -> str:
    label = task.service_type.name if task.service_type else TASK_LABELS.get(task.type, task.type)
    price = task.price
    if price is None and task.service_type_id:
        svc = db.query(models.ServiceType).filter(models.ServiceType.id == task.service_type_id).first()
        if svc:
            price = svc.price
    price_fmt = f"R$ {price / 100:.2f}".replace(".", ",") if price else "a combinar"
    desc = task.description or ""
    apt = task.resident.apartment

    status_labels = {
        "aceito": "Aceito",
        "em_execucao": "Em execução",
        "concluido": "Concluído",
        "recebido": "Recebido",
    }
    next_status = VALID_TRANSITIONS.get(task.status)
    next_labels = {
        "em_execucao": "Iniciar",
        "concluido": "Concluído",
        "recebido": "Recebido",
    }

    btn_html = ""
    cancel_html = ""
    if next_status:
        btn_label = next_labels.get(next_status, next_status)
        btn_html = f'<button class="btn-primary" onclick="avancar()">{btn_label}</button>'
    if task.status in ("aceito", "em_execucao"):
        cancel_html = '<button class="btn-cancel" onclick="cancelar()">Cancelar</button>'

    status_atual = status_labels.get(task.status, task.status)

    return f"""<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<title>Tarefa — Postino</title>
<style>
  * {{ box-sizing: border-box; margin: 0; padding: 0; }}
  html, body {{ height: 100%; }}
  body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f1f5f9; display: flex; flex-direction: column; height: 100%; }}
  .header {{ background: #2563eb; color: #fff; padding: 16px 20px; display: flex; align-items: center; flex-shrink: 0; }}
  .header-logo {{ font-size: 20px; font-weight: 700; letter-spacing: -0.5px; }}
  .header-name {{ font-size: 14px; opacity: 0.85; margin-left: auto; }}
  .card {{ background: #fff; border-radius: 12px; margin: 16px 16px 0; padding: 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); flex-shrink: 0; }}
  .tag {{ display: inline-block; background: #dbeafe; color: #1d4ed8; font-size: 12px; font-weight: 600; padding: 3px 10px; border-radius: 20px; margin-bottom: 12px; }}
  .task-type {{ font-size: 22px; font-weight: 700; color: #0f172a; margin-bottom: 4px; }}
  .task-price {{ font-size: 18px; color: #16a34a; font-weight: 600; margin-bottom: 12px; }}
  .info-row {{ display: flex; align-items: center; gap: 8px; color: #475569; font-size: 14px; margin-bottom: 6px; }}
  .desc {{ color: #64748b; font-size: 14px; margin-top: 12px; padding-top: 12px; border-top: 1px solid #f1f5f9; }}
  .status-badge {{ display: inline-flex; align-items: center; gap: 6px; background: #f0fdf4; color: #15803d; border: 1px solid #bbf7d0; border-radius: 20px; padding: 4px 14px; font-size: 13px; font-weight: 600; margin-top: 12px; }}
  .actions {{ margin: 12px 16px 0; display: flex; gap: 10px; flex-shrink: 0; }}
  .btn-primary {{ flex: 1; padding: 14px; background: #2563eb; color: #fff; border: none; border-radius: 10px; font-size: 15px; font-weight: 600; cursor: pointer; transition: background 0.15s; }}
  .btn-primary:active {{ background: #1d4ed8; }}
  .btn-primary:disabled {{ background: #93c5fd; cursor: not-allowed; }}
  .btn-cancel {{ padding: 14px 16px; background: #fff; color: #dc2626; border: 1.5px solid #fca5a5; border-radius: 10px; font-size: 14px; font-weight: 600; cursor: pointer; white-space: nowrap; }}
  .chat-section {{ margin: 12px 16px 0; display: flex; flex-direction: column; flex: 1; min-height: 0; }}
  .chat-title {{ font-size: 14px; font-weight: 600; color: #475569; margin-bottom: 8px; flex-shrink: 0; }}
  .messages {{ background: #fff; border-radius: 12px; padding: 12px; overflow-y: auto; display: flex; flex-direction: column; gap: 8px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); flex: 1; min-height: 0; }}
  .msg {{ max-width: 78%; padding: 8px 12px; border-radius: 14px; font-size: 14px; line-height: 1.4; }}
  .msg.parceiro {{ align-self: flex-end; background: #2563eb; color: #fff; border-bottom-right-radius: 4px; }}
  .msg.morador {{ align-self: flex-start; background: #f1f5f9; color: #0f172a; border-bottom-left-radius: 4px; }}
  .msg-input-row {{ display: flex; gap: 8px; padding: 12px 16px; background: #fff; border-top: 1px solid #e2e8f0; flex-shrink: 0; }}
  .msg-input {{ flex: 1; padding: 10px 14px; border: 1.5px solid #e2e8f0; border-radius: 10px; font-size: 14px; outline: none; }}
  .msg-input:focus {{ border-color: #2563eb; }}
  .msg-send {{ padding: 10px 18px; background: #2563eb; color: #fff; border: none; border-radius: 10px; font-size: 14px; font-weight: 600; cursor: pointer; }}
  .empty {{ color: #94a3b8; font-size: 13px; text-align: center; padding: 16px 0; }}
  .toast {{ position: fixed; bottom: 80px; left: 50%; transform: translateX(-50%); background: #0f172a; color: #fff; padding: 10px 20px; border-radius: 8px; font-size: 14px; opacity: 0; transition: opacity 0.3s; pointer-events: none; z-index: 100; }}
  .toast.show {{ opacity: 1; }}
</style>
</head>
<body>
<div class="header">
  <div class="header-logo">Postino</div>
  <div class="header-name">{runner.name.split()[0]}</div>
</div>

<div class="card">
  <span class="tag">Tarefa</span>
  <div class="task-type">{label}</div>
  <div class="task-price">{price_fmt}</div>
  <div class="info-row">
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 10c0 7-9 13-9 13s-9-6-9-13a9 9 0 0 1 18 0z"/><circle cx="12" cy="10" r="3"/></svg>
    Local: {apt}
  </div>
  {'<div class="desc">' + desc + '</div>' if desc else ''}
  <div class="status-badge">
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2.5"><polyline points="20 6 9 17 4 12"/></svg>
    {status_atual}
  </div>
</div>

<div class="actions">
  {btn_html}
  {cancel_html}
</div>

{'<div class="chat-section"><div class="chat-title">Chat com solicitante</div><div class="messages" id="msgs"><div class="empty">Carregando...</div></div></div><div class="msg-input-row"><input class="msg-input" id="txt" placeholder="Mensagem..." /><button class="msg-send" onclick="enviar()">Enviar</button></div>' if task.status in ('aceito', 'em_execucao') else ''}

<div class="toast" id="toast"></div>

<script>
const TOKEN = '{token}';

function showToast(msg) {{
  const t = document.getElementById('toast');
  t.textContent = msg;
  t.classList.add('show');
  setTimeout(() => t.classList.remove('show'), 2500);
}}

async function avancar() {{
  const btn = document.querySelector('.btn-primary');
  if (btn) btn.disabled = true;
  try {{
    const r = await fetch('/t/' + TOKEN + '/status', {{method: 'PATCH'}});
    if (r.ok) {{ location.reload(); }}
    else {{ const d = await r.json(); showToast(d.detail || 'Erro'); if (btn) btn.disabled = false; }}
  }} catch(e) {{ showToast('Erro de conexão'); if (btn) btn.disabled = false; }}
}}

async function cancelar() {{
  if (!confirm('Cancelar esta tarefa?')) return;
  const r = await fetch('/t/' + TOKEN + '/cancel', {{method: 'POST'}});
  if (r.ok) {{ showToast('Tarefa cancelada'); setTimeout(() => location.reload(), 1000); }}
  else {{ showToast('Erro ao cancelar'); }}
}}

async function carregarMsgs() {{
  const box = document.getElementById('msgs');
  if (!box) return;
  try {{
    const r = await fetch('/t/' + TOKEN + '/messages');
    const msgs = await r.json();
    if (msgs.length === 0) {{
      box.innerHTML = '<div class="empty">Nenhuma mensagem ainda.</div>';
    }} else {{
      box.innerHTML = msgs.map(m =>
        `<div class="msg ${{m.sender}}">${{m.type === 'image' ? '[imagem]' : m.content}}</div>`
      ).join('');
      box.scrollTop = box.scrollHeight;
    }}
  }} catch(e) {{}}
}}

async function enviar() {{
  const inp = document.getElementById('txt');
  const txt = inp.value.trim();
  if (!txt) return;
  inp.value = '';
  const r = await fetch('/t/' + TOKEN + '/message', {{
    method: 'POST',
    headers: {{'Content-Type': 'application/json'}},
    body: JSON.stringify({{content: txt}}),
  }});
  if (r.ok) {{ carregarMsgs(); }}
  else {{ showToast('Erro ao enviar'); }}
}}

document.getElementById('txt') && document.getElementById('txt').addEventListener('keydown', e => {{
  if (e.key === 'Enter') enviar();
}});

if (document.getElementById('msgs')) {{
  carregarMsgs();
  setInterval(carregarMsgs, 5000);
}}
</script>
</body>
</html>"""


def _render_assumida() -> str:
    return """<!DOCTYPE html>
<html lang="pt-BR">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Tarefa — Postino</title>
<style>
  body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; background: #f1f5f9; min-height: 100vh; display: flex; flex-direction: column; }
  .header { background: #2563eb; color: #fff; padding: 16px 20px; font-size: 20px; font-weight: 700; }
  .card { background: #fff; border-radius: 12px; margin: 24px 16px; padding: 28px 20px; box-shadow: 0 1px 4px rgba(0,0,0,0.08); text-align: center; }
  .icon { font-size: 40px; margin-bottom: 16px; }
  h2 { font-size: 18px; color: #0f172a; margin-bottom: 8px; }
  p { color: #64748b; font-size: 14px; line-height: 1.5; }
</style>
</head>
<body>
<div class="header">Postino</div>
<div class="card">
  <div class="icon">
    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#94a3b8" stroke-width="1.5"><circle cx="12" cy="12" r="10"/><line x1="12" y1="8" x2="12" y2="12"/><line x1="12" y1="16" x2="12.01" y2="16"/></svg>
  </div>
  <h2>Tarefa já assumida</h2>
  <p>Outro parceiro chegou primeiro. Fique atento — novas tarefas chegam por aqui!</p>
</div>
</body>
</html>"""


@router.get("/{token}", response_class=HTMLResponse)
def abrir_link(token: str, db: Session = Depends(get_db)):
    link = _get_link(token, db)
    runner = link.runner
    task = link.task

    if task.status == "cancelado":
        return HTMLResponse(content=_render_assumida(), status_code=200)

    # Tarefa já pertence a este parceiro
    if task.runner_id == runner.id:
        return HTMLResponse(content=_render_page(token, runner, task, db))

    # Tarefa já foi pega por outro
    if task.runner_id is not None:
        return HTMLResponse(content=_render_assumida())

    # Tenta aceitar atomicamente
    result = db.execute(
        sql_update(models.Task)
        .where(
            models.Task.id == task.id,
            models.Task.runner_id == None,
            models.Task.status == "solicitado",
        )
        .values(runner_id=runner.id, status="aceito", updated_at=datetime.now(timezone.utc))
    )
    db.commit()

    if result.rowcount == 0:
        return HTMLResponse(content=_render_assumida())

    db.refresh(task)

    # Notifica residente
    try:
        phone = wa_phone(task.resident.phone)
        send_message(phone, f"*{runner.name}* aceitou sua tarefa. Você já pode mandar uma mensagem aqui mesmo.")
        if runner.photo_url:
            photo_path = pathlib.Path(runner.photo_url)
            if photo_path.exists():
                photo_bytes = photo_path.read_bytes()
                media_id = upload_media(photo_bytes, "image/jpeg", "parceiro.jpg")
                if media_id:
                    send_image(phone, media_id)
    except Exception as e:
        log.error(f"Erro ao notificar residente: {e}")

    return HTMLResponse(content=_render_page(token, runner, task, db))


@router.patch("/{token}/status")
def avancar_status(token: str, db: Session = Depends(get_db)):
    link = _get_link(token, db)
    runner = link.runner
    task = link.task

    if task.runner_id != runner.id:
        raise HTTPException(status_code=403, detail="Esta tarefa não é sua")

    next_status = VALID_TRANSITIONS.get(task.status)
    if not next_status:
        raise HTTPException(status_code=400, detail="Nenhuma transição disponível")

    task.status = next_status
    task.updated_at = datetime.now(timezone.utc)
    db.commit()

    NOTIFICACOES = {
        "em_execucao": lambda r, t, d: f"*{r.name}* iniciou a execução da sua tarefa.",
        "concluido": _msg_concluido,
        "recebido": lambda r, t, d: f"Como você avalia o serviço de *{r.name}*?\n\nResponda com um número de 1 a 5:\n1 - Ruim\n2 - Regular\n3 - Bom\n4 - Ótimo\n5 - Excelente",
    }
    msg_fn = NOTIFICACOES.get(next_status)
    if msg_fn:
        try:
            send_message(wa_phone(task.resident.phone), msg_fn(runner, task, db))
        except Exception as e:
            log.error(f"Erro ao notificar residente: {e}")

    return {"status": next_status}


@router.post("/{token}/cancel")
def cancelar_tarefa(token: str, db: Session = Depends(get_db)):
    link = _get_link(token, db)
    runner = link.runner
    task = link.task

    if task.runner_id != runner.id:
        raise HTTPException(status_code=403, detail="Esta tarefa não é sua")

    if task.status not in ("aceito", "em_execucao"):
        raise HTTPException(status_code=400, detail="Tarefa não pode ser cancelada neste status")

    task.status = "solicitado"
    task.runner_id = None
    task.updated_at = datetime.now(timezone.utc)
    db.commit()

    try:
        send_message(
            wa_phone(task.resident.phone),
            "O parceiro precisou cancelar sua tarefa. Estamos buscando outro parceiro disponível.\n\nSe quiser cancelar, é só responder *cancelar*.",
        )
    except Exception as e:
        log.error(f"Erro ao notificar residente: {e}")

    return {"status": "solicitado"}


@router.get("/{token}/messages")
def get_messages(token: str, db: Session = Depends(get_db)):
    link = _get_link(token, db)
    task = link.task

    messages = db.query(models.TaskMessage).filter(
        models.TaskMessage.task_id == task.id,
    ).order_by(models.TaskMessage.created_at.asc()).all()

    return [
        {"id": m.id, "sender": m.sender, "type": m.type, "content": m.content, "created_at": m.created_at}
        for m in messages
    ]


class TextMessage(BaseModel):
    content: str


@router.post("/{token}/message")
def send_text(token: str, body: TextMessage, db: Session = Depends(get_db)):
    link = _get_link(token, db)
    runner = link.runner
    task = link.task

    if task.runner_id != runner.id:
        raise HTTPException(status_code=403, detail="Esta tarefa não é sua")
    if task.status not in ("aceito", "em_execucao"):
        raise HTTPException(status_code=400, detail="Tarefa não está ativa")

    db.add(models.TaskMessage(task_id=task.id, sender="parceiro", type="text", content=body.content))
    db.commit()
    send_message(wa_phone(task.resident.phone), body.content)
    return {"status": "ok"}
