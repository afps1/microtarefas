import os
import json
import urllib.request
import urllib.parse
from dotenv import load_dotenv

load_dotenv()

WHATSAPP_TOKEN = os.getenv("WHATSAPP_TOKEN")
WHATSAPP_MSG_URL = os.getenv("WHATSAPP_MSG_URL")
WHATSAPP_MEDIA_URL = os.getenv("WHATSAPP_MEDIA_URL")


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


def send_image(to: str, media_id: str):
    """Envia imagem via WhatsApp usando media_id já hospedado na Meta."""
    payload = json.dumps({
        "messaging_product": "whatsapp",
        "to": to,
        "type": "image",
        "image": {"id": media_id},
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
        logging.getLogger(__name__).error(f"Erro ao enviar imagem WhatsApp para {to}: {e}")
        return None


def upload_media(file_bytes: bytes, mime_type: str, filename: str) -> str | None:
    """Faz upload de mídia para a Meta e retorna o media_id."""
    import io
    boundary = "----FormBoundary"
    body = (
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="messaging_product"\r\n\r\n'
        f"whatsapp\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="type"\r\n\r\n'
        f"{mime_type}\r\n"
        f"--{boundary}\r\n"
        f'Content-Disposition: form-data; name="file"; filename="{filename}"\r\n'
        f"Content-Type: {mime_type}\r\n\r\n"
    ).encode() + file_bytes + f"\r\n--{boundary}--\r\n".encode()

    req = urllib.request.Request(
        WHATSAPP_MEDIA_URL,
        data=body,
        headers={
            "Content-Type": f"multipart/form-data; boundary={boundary}",
            "Authorization": f"Bearer {WHATSAPP_TOKEN}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            data = json.loads(res.read())
            return data.get("id")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Erro ao fazer upload de mídia: {e}")
        return None


def get_media_download_url(media_id: str) -> tuple[str, str] | tuple[None, None]:
    """Busca a URL de download e mime_type de uma mídia pelo ID."""
    req = urllib.request.Request(
        f"https://graph.facebook.com/v18.0/{media_id}",
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read())
            return data.get("url"), data.get("mime_type", "image/jpeg")
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Erro ao buscar URL de mídia {media_id}: {e}")
        return None, None


def download_media_bytes(url: str) -> bytes | None:
    """Baixa os bytes de uma mídia da Meta."""
    req = urllib.request.Request(
        url,
        headers={"Authorization": f"Bearer {WHATSAPP_TOKEN}"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as res:
            return res.read()
    except Exception as e:
        import logging
        logging.getLogger(__name__).error(f"Erro ao baixar mídia: {e}")
        return None
