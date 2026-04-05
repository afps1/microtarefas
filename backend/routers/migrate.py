"""
Endpoint temporário de migração — remover após uso.
"""
from fastapi import APIRouter, Depends
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
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS service_type_id INT NULL",
        "ALTER TABLE tasks ADD COLUMN IF NOT EXISTS price INT NULL",
    ]

    results = []
    for sql in sqls:
        try:
            db.execute(text(sql))
            db.commit()
            results.append({"sql": sql[:60], "status": "ok"})
        except Exception as e:
            results.append({"sql": sql[:60], "status": str(e)})

    return {"results": results}
