import os
import logging

logger = logging.getLogger(__name__)

RESEND_API_KEY = os.getenv("RESEND_API_KEY", "")


def send_otp_email(email: str, code: str):
    if not RESEND_API_KEY:
        logger.warning("[EMAIL] RESEND_API_KEY não configurada — fallback mock")
        logger.info(f"[EMAIL MOCK] Para: {email} | OTP: {code}")
        return

    try:
        import resend
        resend.api_key = RESEND_API_KEY

        resend.Emails.send({
            "from": "Postino <noreply@postino.com.br>",
            "to": [email],
            "subject": "Seu código de acesso — Postino",
            "html": f"""
                <div style="font-family:sans-serif;max-width:400px;margin:0 auto;padding:32px 24px;">
                  <h2 style="color:#2563eb;margin-bottom:8px;">Postino</h2>
                  <p style="color:#334155;font-size:15px;margin-bottom:24px;">Use o código abaixo para acessar o app:</p>
                  <div style="background:#f1f5f9;border-radius:8px;padding:20px;text-align:center;font-size:32px;font-weight:800;letter-spacing:8px;color:#0f172a;">
                    {code}
                  </div>
                  <p style="color:#94a3b8;font-size:13px;margin-top:24px;">O código expira em 10 minutos. Se não foi você, ignore este e-mail.</p>
                </div>
            """,
        })
        logger.info(f"[EMAIL] OTP enviado para {email}")

    except Exception as e:
        logger.error(f"[EMAIL] Erro ao enviar para {email}: {e}")
        raise
