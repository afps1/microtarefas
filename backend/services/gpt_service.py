import os
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")

TASK_TYPES = ["lixo", "encomenda", "mercadinho", "outro"]

SYSTEM_PROMPT = """Você é um assistente do app Vem Aqui, plataforma de microtarefas em condomínios.
O morador enviou uma mensagem pelo WhatsApp. Identifique a intenção.

Responda APENAS com um JSON no formato:
{
  "intent": "solicitar_tarefa" | "cancelar" | "status" | "outro",
  "task_type": "lixo" | "encomenda" | "mercadinho" | "outro" | null,
  "description": "detalhes adicionais extraídos da mensagem ou null"
}

Exemplos de intent:
- "quero levar o lixo" → solicitar_tarefa, lixo
- "pega minha encomenda na portaria" → solicitar_tarefa, encomenda
- "quero comprar no mercadinho" → solicitar_tarefa, mercadinho
- "cancela meu pedido" → cancelar
- "qual o status do meu pedido" → status
- qualquer outra coisa → outro
"""


def interpret_message(text: str) -> dict:
    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": text},
        ],
        "temperature": 0,
        "max_tokens": 200,
    }).encode()

    req = urllib.request.Request(
        API_URL,
        data=payload,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",
        },
    )

    try:
        with urllib.request.urlopen(req, timeout=10) as res:
            data = json.loads(res.read())
            content = data["choices"][0]["message"]["content"].strip()
            # Remove markdown code block se o modelo retornar com ```json
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
    except Exception as e:
        return {"intent": "outro", "task_type": None, "description": None, "error": str(e)}
