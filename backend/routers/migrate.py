"""
Endpoint temporário de migração — remover após uso.
"""
from fastapi import APIRouter, Depends, UploadFile, File
from sqlalchemy import text
from sqlalchemy.orm import Session
from database import get_db
import os

router = APIRouter(prefix="/migrate", tags=["migrate"])


@router.post("/run")
def run_migration(key: str, db: Session = Depends(get_db)):
    if key != os.getenv("SETUP_KEY"):
        return {"error": "unauthorized"}

    sqls = [
        """CREATE TABLE IF NOT EXISTS pending_requests (
            id INT AUTO_INCREMENT PRIMARY KEY,
            resident_id INT NOT NULL UNIQUE,
            task_type VARCHAR(100) NOT NULL,
            service_type_id INT NULL,
            description TEXT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (resident_id) REFERENCES residents(id),
            FOREIGN KEY (service_type_id) REFERENCES service_types(id)
        )""",
        """CREATE TABLE IF NOT EXISTS service_types (
            id INT AUTO_INCREMENT PRIMARY KEY,
            condominium_id INT NOT NULL,
            name VARCHAR(200) NOT NULL,
            description VARCHAR(500),
            price INT NOT NULL,
            active BOOLEAN DEFAULT TRUE,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (condominium_id) REFERENCES condominiums(id)
        )""",
        """CREATE TABLE IF NOT EXISTS ratings (
            id INT AUTO_INCREMENT PRIMARY KEY,
            task_id INT NOT NULL UNIQUE,
            runner_id INT NOT NULL,
            resident_id INT NOT NULL,
            score INT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id),
            FOREIGN KEY (runner_id) REFERENCES runners(id),
            FOREIGN KEY (resident_id) REFERENCES residents(id)
        )""",
        """CREATE TABLE IF NOT EXISTS push_subscriptions (
            id INT AUTO_INCREMENT PRIMARY KEY,
            runner_id INT NOT NULL UNIQUE,
            endpoint TEXT NOT NULL,
            p256dh TEXT NOT NULL,
            auth TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (runner_id) REFERENCES runners(id)
        )""",
        """CREATE TABLE IF NOT EXISTS task_messages (
            id INT AUTO_INCREMENT PRIMARY KEY,
            task_id INT NOT NULL,
            sender ENUM('parceiro','morador') NOT NULL,
            type ENUM('text','image') NOT NULL DEFAULT 'text',
            content TEXT NOT NULL,
            created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (task_id) REFERENCES tasks(id)
        )""",
    ]

    # Adiciona colunas apenas se não existirem
    col_checks = [
        ("tasks", "service_type_id", "INT NULL"),
        ("tasks", "price", "INT NULL"),
        ("pending_requests", "awaiting_observation", "BOOLEAN NOT NULL DEFAULT FALSE"),
        ("runners", "available", "BOOLEAN NOT NULL DEFAULT TRUE"),
    ]

    results = []
    for sql in sqls:
        try:
            db.execute(text(sql))
            db.commit()
            results.append({"sql": sql[:60], "status": "ok"})
        except Exception as e:
            results.append({"sql": sql[:60], "status": str(e)})

    for table, column, col_def in col_checks:
        check = db.execute(text(
            f"SELECT COUNT(*) FROM information_schema.COLUMNS "
            f"WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = '{table}' AND COLUMN_NAME = '{column}'"
        )).scalar()
        if check == 0:
            try:
                db.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_def}"))
                db.commit()
                results.append({"sql": f"ADD COLUMN {table}.{column}", "status": "ok"})
            except Exception as e:
                results.append({"sql": f"ADD COLUMN {table}.{column}", "status": str(e)})
        else:
            results.append({"sql": f"ADD COLUMN {table}.{column}", "status": "already exists"})

    # Altera Enum de status das tarefas para incluir 'cancelado'
    alter_sql = "ALTER TABLE tasks MODIFY COLUMN status ENUM('solicitado','aceito','em_execucao','concluido','recebido','cancelado') NOT NULL DEFAULT 'solicitado'"
    try:
        db.execute(text(alter_sql))
        db.commit()
        results.append({"sql": "ALTER TABLE tasks status enum", "status": "ok"})
    except Exception as e:
        results.append({"sql": "ALTER TABLE tasks status enum", "status": str(e)})

    return {"results": results}


@router.post("/test-email")
def test_email(key: str, email: str):
    if key != os.getenv("SETUP_KEY"):
        return {"error": "unauthorized"}
    import urllib.request, json
    api_key = os.getenv("RESEND_API_KEY", "")
    if not api_key:
        return {"error": "RESEND_API_KEY não configurada"}
    try:
        payload = json.dumps({
            "from": "Postino <noreply@postino.com.br>",
            "to": [email],
            "subject": "Teste Postino",
            "html": "<p>Teste de envio — funcionou!</p>",
        }).encode("utf-8")
        req = urllib.request.Request(
            "https://api.resend.com/emails",
            data=payload,
            headers={"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"},
        )
        with urllib.request.urlopen(req) as resp:
            body = json.loads(resp.read())
            return {"status": "ok", "resend_response": body}
    except urllib.error.HTTPError as e:
        error_body = e.read().decode()
        return {"status": "error", "http_status": e.code, "detail": error_body}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


@router.post("/upload-video")
async def upload_video(key: str, file: UploadFile = File(...)):
    if key != os.getenv("SETUP_KEY"):
        return {"error": "unauthorized"}
    data = await file.read()
    with open("/data/postino.mp4", "wb") as f:
        f.write(data)
    return {"status": "ok", "size": len(data)}


@router.post("/clean-tasks")
def clean_tasks(key: str, db: Session = Depends(get_db)):
    if key != os.getenv("SETUP_KEY"):
        return {"error": "unauthorized"}

    db.execute(text("DELETE FROM task_messages"))
    db.execute(text("DELETE FROM ratings"))
    db.execute(text("DELETE FROM magic_links"))
    db.execute(text("DELETE FROM pending_requests"))
    db.execute(text("DELETE FROM tasks"))
    db.commit()
    return {"status": "ok", "message": "Tarefas, mensagens, magic links e avaliações removidos."}
