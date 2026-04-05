import logging

logger = logging.getLogger(__name__)


def send_otp_email(email: str, code: str):
    """
    MOCKED — em produção integrar com SendGrid, Resend, ou SMTP.
    """
    logger.info(f"[EMAIL MOCK] Para: {email} | OTP: {code}")
    print(f"[EMAIL MOCK] Para: {email} | OTP: {code}")
