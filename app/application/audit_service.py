import json
from typing import Any
from sqlalchemy.orm import Session
from app.infrastructure.models import AuditLogModel


def registrar_auditoria(
    db: Session,
    acao: str,
    entidade: str,
    entidade_id: int | None = None,
    usuario_id: int | None = None,
    detalhes: dict[str, Any] | None = None,
) -> AuditLogModel:
    log = AuditLogModel(
        usuario_id=usuario_id,
        acao=acao,
        entidade=entidade,
        entidade_id=entidade_id,
        detalhes=json.dumps(detalhes or {}, ensure_ascii=False, default=str),
    )
    db.add(log)
    return log


def listar_logs_auditoria(
    db: Session,
    page: int = 1,
    limit: int = 20,
    acao: str | None = None,
) -> tuple[list[AuditLogModel], int]:
    query = db.query(AuditLogModel)
    if acao:
        query = query.filter(AuditLogModel.acao == acao)

    total = query.count()
    itens = (
        query.order_by(AuditLogModel.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return itens, total