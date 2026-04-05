from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime, timezone
from database import get_db
from dependencies import get_current_runner
import models

router = APIRouter(prefix="/tasks", tags=["tasks"])

VALID_TRANSITIONS = {
    "solicitado": "aceito",
    "aceito": "em_execucao",
    "em_execucao": "concluido",
    "concluido": "recebido",
}


class StatusUpdate(BaseModel):
    status: str


@router.get("/my")
def my_tasks(db: Session = Depends(get_db), runner=Depends(get_current_runner)):
    """Retorna tarefas do condomínio do parceiro — pendentes + as suas em andamento."""
    tasks = (
        db.query(models.Task)
        .filter(
            models.Task.condominium_id == runner.condominium_id,
            models.Task.status.in_(["solicitado", "aceito", "em_execucao", "concluido"]),
        )
        .filter(
            (models.Task.runner_id == None) | (models.Task.runner_id == runner.id)
        )
        .order_by(models.Task.created_at.desc())
        .all()
    )

    return [
        {
            "id": t.id,
            "type": t.type,
            "description": t.description,
            "status": t.status,
            "resident_name": t.resident.name,
            "resident_apartment": t.resident.apartment,
            "created_at": t.created_at,
            "is_mine": t.runner_id == runner.id,
        }
        for t in tasks
    ]


@router.patch("/{task_id}/status")
def update_task_status(
    task_id: int,
    body: StatusUpdate,
    db: Session = Depends(get_db),
    runner=Depends(get_current_runner),
):
    task = db.query(models.Task).filter(
        models.Task.id == task_id,
        models.Task.condominium_id == runner.condominium_id,
    ).first()

    if not task:
        raise HTTPException(status_code=404, detail="Tarefa não encontrada")

    expected_next = VALID_TRANSITIONS.get(task.status)

    if body.status != expected_next:
        raise HTTPException(
            status_code=400,
            detail=f"Transição inválida: {task.status} → {body.status}",
        )

    # Ao aceitar: reserva a tarefa para este parceiro (transacional)
    if body.status == "aceito":
        if task.runner_id is not None and task.runner_id != runner.id:
            raise HTTPException(status_code=409, detail="Tarefa já foi aceita por outro parceiro")
        task.runner_id = runner.id

    # Garante que só quem aceitou pode avançar
    if task.runner_id and task.runner_id != runner.id:
        raise HTTPException(status_code=403, detail="Esta tarefa pertence a outro parceiro")

    task.status = body.status
    task.updated_at = datetime.now(timezone.utc)
    db.commit()

    return {"id": task.id, "status": task.status}
