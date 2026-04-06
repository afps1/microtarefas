#!/usr/bin/env python3
"""
Roda UMA VEZ para gerar as chaves VAPID.
Adicione as duas variáveis geradas no Railway.
"""
import base64
from cryptography.hazmat.primitives.asymmetric import ec
from cryptography.hazmat.primitives import serialization

key = ec.generate_private_key(ec.SECP256R1())

private_pem = key.private_bytes(
    serialization.Encoding.PEM,
    serialization.PrivateFormat.TraditionalOpenSSL,
    serialization.NoEncryption(),
).decode().strip()

public_raw = key.public_key().public_bytes(
    serialization.Encoding.X962,
    serialization.PublicFormat.UncompressedPoint,
)
public_b64 = base64.urlsafe_b64encode(public_raw).decode().rstrip("=")

print("=== Adicione estas variáveis no Railway ===\n")
print(f"VAPID_PUBLIC_KEY={public_b64}\n")
print(f"VAPID_PRIVATE_KEY (cole exatamente assim, incluindo \\n):")
print(private_pem)
