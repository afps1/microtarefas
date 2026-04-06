import os
import json
import logging
from pywebpush import webpush, WebPushException

log = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "").replace("\\n", "\n")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_CLAIMS = {"sub": "mailto:admin@microtarefas.com"}


def send_push(subscription: dict, title: str, body: str):
    if not VAPID_PRIVATE_KEY:
        log.warning("VAPID_PRIVATE_KEY não configurada — push ignorado")
        return
    if not subscription.get("endpoint"):
        log.warning("Subscription sem endpoint — push ignorado")
        return
    log.warning(f"Enviando push para {subscription['endpoint'][:60]}...")
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps({"title": title, "body": body}),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
        )
        log.warning("Push enviado com sucesso")
    except WebPushException as e:
        log.error(f"WebPushException: {repr(e)}")
    except Exception as e:
        log.error(f"Erro ao enviar push: {repr(e)}")
