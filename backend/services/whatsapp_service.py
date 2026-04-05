import os
import json
import urllib.request
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_MSG_URL = os.getenv("WHATSAPP_MSG_URL")


def send_message(to: str, text: str):
    """Envia mensagem de texto via WhatsApp API da Meta."""
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "text",
        "text": {"body": text},
    }).encode()

    req = urllib.request.Request(
        WHATSAPP_MSG_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            return json.loads(res.read())
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Erro ao enviar WhatsApp para {to}: {e}")
        return None
