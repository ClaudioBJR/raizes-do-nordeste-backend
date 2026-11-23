import json
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from app.api.dependencies import exigir_perfis, obter_usuario_atual
from app.api.schemas import AuditLogOut, FidelidadeContaOut, FidelidadeMovOut
from app.application import audit_service, fidelidade_relatorio_service
from app.domain.enums import PerfilUsuario
from app.infrastructure.database import get_db
from app.infrastructure.models import UsuarioModel

router = APIRouter(tags=["Fidelidade, Matriz e Auditoria"])


@router.get("/fidelidade/me", response_model=FidelidadeContaOut, summary="Consultar saldo de pontos, nivel e historico de fidelidade")
def minha_fidelidade(
    db: Session = Depends(get_db),
    usuario: UsuarioModel = Depends(obter_usuario_atual),
):
    conta = fidelidade_relatorio_service.consultar_minha_fidelidade(db=db, usuario=usuario)
    return FidelidadeContaOut(
        usuarioId=conta.usuario_id,
        saldoPontos=conta.saldo_pontos,
        totalPedidosPagos=conta.total_pedidos_pagos,
        nivel=conta.nivel,
        historico=[
            FidelidadeMovOut(
                id=m.id,
                pedidoId=m.pedido_id,
                tipo=m.tipo,
                pontos=m.pontos,
                criadoEm=m.criado_em,
            )
            for m in conta.movimentacoes
        ],
    )


@router.get("/relatorios/matriz", summary="Relatorio consolidado de vendas por unidade, regiao, canal e produtos (GERENTE/MATRIZ)")
def relatorio_matriz(
    db: Session = Depends(get_db),
    _usuario: UsuarioModel = Depends(exigir_perfis(PerfilUsuario.GERENTE, PerfilUsuario.MATRIZ)),
):
    return fidelidade_relatorio_service.gerar_relatorio_consolidado_matriz(db=db)


@router.get("/auditoria/logs", summary="Consultar trilha de auditoria de acoes sensiveis (GERENTE/MATRIZ)")
def listar_auditoria(
    page: int = Query(1, ge=1),
    limit: int = Query(20, ge=1, le=100),
    acao: str | None = Query(None, description="Ex.: PEDIDO_CRIADO, PAGAMENTO_APROVADO, PEDIDO_CANCELADO"),
    db: Session = Depends(get_db),
    _usuario: UsuarioModel = Depends(exigir_perfis(PerfilUsuario.GERENTE, PerfilUsuario.MATRIZ)),
):
    logs, total = audit_service.listar_logs_auditoria(db=db, page=page, limit=limit, acao=acao)
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "items": [
            AuditLogOut(
                id=log.id,
                usuarioId=log.usuario_id,
                acao=log.acao,
                entidade=log.entidade,
                entidadeId=log.entidade_id,
                detalhes=json.loads(log.detalhes) if log.detalhes else {},
                criadoEm=log.criado_em,
            )
            for log in logs
        ],
    }