import os
import json
import urllib.request
import urllib.error
from dotenv import load_dotenv

load_dotenv()

API_KEY = os.getenv("OPENAI_API_KEY")
MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
API_URL = os.getenv("OPENAI_API_URL", "https://api.openai.com/v1/chat/completions")


def interpret_message(text: str, services: list[str] | None = None) -> dict:
    if services:
        services_list = "\n".join(f'- "{s}"' for s in services)
        task_type_options = " | ".join(f'"{s}"' for s in services) + ' | "outro"'
        services_section = f"""
Os serviços disponíveis neste condomínio são:
{services_list}

Ao identificar uma solicitação de tarefa, retorne em task_type o nome EXATO do serviço acima que melhor corresponde à mensagem do morador, ou "outro" se nenhum corresponder.
"""
    else:
        task_type_options = '"outro"'
        services_section = 'Não há serviços cadastrados. Use task_type "outro".'

    system_prompt = f"""Você é um assistente do app Vem Aqui, plataforma de microtarefas em condomínios.
O morador enviou uma mensagem pelo WhatsApp. Identifique a intenção.
{services_section}
Responda APENAS com um JSON no formato:
{{
  "intent": "solicitar_tarefa" | "cancelar" | "status" | "outro",
  "task_type": {task_type_options} | null,
  "description": "detalhes adicionais extraídos da mensagem ou null"
}}

Exemplos de intent:
- qualquer pedido de execução de tarefa → solicitar_tarefa
- "cancela meu pedido" → cancelar
- "qual o status do meu pedido" → status
- qualquer outra coisa → outro
"""

    payload = json.dumps({
        "model": MODEL,
        "messages": [
            {"role": "system", "content": system_prompt},
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
            if content.startswith("```"):
                content = content.split("```")[1]
                if content.startswith("json"):
                    content = content[4:]
            return json.loads(content)
    except Exception as e:
        return {"intent": "outro", "task_type": None, "description": None, "error": str(e)}
