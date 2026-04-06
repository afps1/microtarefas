import os
import json
import logging
from pywebpush import webpush, WebPushException

log = logging.getLogger(__name__)

VAPID_PRIVATE_KEY = os.getenv("VAPID_PRIVATE_KEY", "").replace("\\n", "\n")
VAPID_PUBLIC_KEY = os.getenv("VAPID_PUBLIC_KEY", "")
VAPID_CLAIMS = {"sub": "mailto:admin@microtarefas.com"}


def send_push(subscription: dict, title: str, body: str):
    if not VAPID_PRIVATE_KEY or not subscription.get("endpoint"):
        return
    try:
        webpush(
            subscription_info=subscription,
            data=json.dumps({"title": title, "body": body}),
            vapid_private_key=VAPID_PRIVATE_KEY,
            vapid_claims=VAPID_CLAIMS,
        )
    except WebPushException as e:
        log.warning(f"Push falhou (subscription expirada?): {e}")
    except Exception as e:
        log.error(f"Erro ao enviar push: {e}")
