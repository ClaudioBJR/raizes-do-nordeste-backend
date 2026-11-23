from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload
from app.domain.enums import StatusPedido
from app.domain.exceptions import RecursoNaoEncontradoError
from app.infrastructure.models import (
    FidelidadeContaModel,
    PedidoItemModel,
    PedidoModel,
    ProdutoModel,
    UnidadeModel,
    UsuarioModel,
)


def consultar_minha_fidelidade(db: Session, usuario: UsuarioModel) -> FidelidadeContaModel:
    if not usuario.consentimento_fidelidade:
        raise RecursoNaoEncontradoError(
            message="Usuario nao aderiu ao programa de fidelizacao (sem consentimento LGPD).",
        )

    conta = (
        db.query(FidelidadeContaModel)
        .options(joinedload(FidelidadeContaModel.movimentacoes))
        .filter(FidelidadeContaModel.usuario_id == usuario.id)
        .first()
    )
    if not conta:
        conta = FidelidadeContaModel(
            usuario_id=usuario.id,
            saldo_pontos=0,
            total_pedidos_pagos=0,
            nivel="BRONZE",
        )
        db.add(conta)
        db.commit()
        db.refresh(conta)
    return conta


def gerar_relatorio_consolidado_matriz(db: Session) -> dict:
    status_validos = [
        StatusPedido.EM_PREPARO.value,
        StatusPedido.PRONTO.value,
        StatusPedido.ENTREGUE.value,
    ]

    totais = (
        db.query(
            func.count(PedidoModel.id),
            func.coalesce(func.sum(PedidoModel.valor_total), 0),
        )
        .filter(PedidoModel.status.in_(status_validos))
        .first()
    )
    total_cancelados = (
        db.query(func.count(PedidoModel.id))
        .filter(PedidoModel.status == StatusPedido.CANCELADO.value)
        .scalar()
        or 0
    )

    por_unidade_rows = (
        db.query(
            UnidadeModel.codigo,
            UnidadeModel.nome,
            UnidadeModel.regiao,
            func.count(PedidoModel.id),
            func.coalesce(func.sum(PedidoModel.valor_total), 0),
        )
        .join(PedidoModel, PedidoModel.unidade_id == UnidadeModel.id)
        .filter(PedidoModel.status.in_(status_validos))
        .group_by(UnidadeModel.id)
        .all()
    )

    por_regiao_rows = (
        db.query(
            UnidadeModel.regiao,
            func.count(PedidoModel.id),
            func.coalesce(func.sum(PedidoModel.valor_total), 0),
        )
        .join(PedidoModel, PedidoModel.unidade_id == UnidadeModel.id)
        .filter(PedidoModel.status.in_(status_validos))
        .group_by(UnidadeModel.regiao)
        .all()
    )

    por_canal_rows = (
        db.query(
            PedidoModel.canal_pedido,
            func.count(PedidoModel.id),
            func.coalesce(func.sum(PedidoModel.valor_total), 0),
        )
        .filter(PedidoModel.status.in_(status_validos))
        .group_by(PedidoModel.canal_pedido)
        .all()
    )

    top_produtos_rows = (
        db.query(
            ProdutoModel.id,
            ProdutoModel.nome,
            func.sum(PedidoItemModel.quantidade).label("qtd_total"),
            func.sum(PedidoItemModel.subtotal).label("receita_total"),
        )
        .join(PedidoItemModel, PedidoItemModel.produto_id == ProdutoModel.id)
        .join(PedidoModel, PedidoModel.id == PedidoItemModel.pedido_id)
        .filter(PedidoModel.status.in_(status_validos))
        .group_by(ProdutoModel.id)
        .order_by(func.sum(PedidoItemModel.quantidade).desc())
        .limit(5)
        .all()
    )

    return {
        "resumoGeral": {
            "totalPedidosPagos": int(totais[0] or 0),
            "faturamentoTotal": float(totais[1] or 0),
            "totalPedidosCancelados": int(total_cancelados),
        },
        "vendasPorUnidade": [
            {
                "codigo": r[0],
                "unidade": r[1],
                "regiao": r[2],
                "totalPedidos": int(r[3]),
                "faturamento": float(r[4]),
            }
            for r in por_unidade_rows
        ],
        "vendasPorRegiao": [
            {
                "regiao": r[0],
                "totalPedidos": int(r[1]),
                "faturamento": float(r[2]),
            }
            for r in por_regiao_rows
        ],
        "vendasPorCanal": [
            {
                "canalPedido": r[0],
                "totalPedidos": int(r[1]),
                "faturamento": float(r[2]),
            }
            for r in por_canal_rows
        ],
        "produtosMaisConsumidos": [
            {
                "produtoId": int(r[0]),
                "nome": r[1],
                "quantidadeVendida": int(r[2]),
                "receitaTotal": float(r[3]),
            }
            for r in top_produtos_rows
        ],
    }