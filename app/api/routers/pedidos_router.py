import json
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.dependencies import exigir_perfis, obter_usuario_atual
from app.api.schemas import (
    AtualizarStatusPedidoIn,
    CancelarPedidoIn,
    PagamentoMockIn,
    PagamentoMockOut,
    PedidoCreateIn,
    PedidoItemOut,
    PedidoOut,
)
from app.application import pagamento_service, pedido_service
from app.domain.enums import CanalPedido, PerfilUsuario, StatusPagamento, StatusPedido
from app.infrastructure.database import get_db
from app.infrastructure.models import PedidoModel, UsuarioModel

router = APIRouter(tags=["Pedidos e Pagamentos"])


def _serializar_pedido(p: PedidoModel) -> PedidoOut:
    return PedidoOut(
        pedidoId=p.id,
        clienteId=p.cliente_id,
        unidadeId=p.unidade_id,
        canalPedido=p.canal_pedido,
        status=p.status,
        subtotal=float(p.subtotal),
        descontoFidelidade=float(p.desconto_fidelidade),
        total=float(p.valor_total),
        formaPagamento=p.forma_pagamento,
        itens=[
            PedidoItemOut(
                produtoId=item.produto_id,
                quantidade=item.quantidade,
                precoUnitario=float(item.preco_unitario),
                subtotal=float(item.subtotal),
            )
            for item in p.itens
        ],
        createdAt=p.criado_em,
    )


@router.post("/pedidos", response_model=PedidoOut, status_code=status.HTTP_201_CREATED, summary="Criar pedido multicanal com validacao e baixa de estoque")
def criar_pedido(
    payload: PedidoCreateIn,
    db: Session = Depends(get_db),
    usuario: UsuarioModel = Depends(
        exigir_perfis(PerfilUsuario.CLIENTE, PerfilUsuario.ATENDENTE, PerfilUsuario.GERENTE)
    ),
):
    pedido = pedido_service.criar_pedido(
        db=db,
        usuario=usuario,
        unidade_id=payload.unidadeId,
        canal_pedido=payload.canalPedido,
        forma_pagamento=payload.formaPagamento,
        itens_payload=[{"produto_id": i.produtoId, "quantidade": i.quantidade} for i in payload.itens],
        usar_pontos_fidelidade=payload.usarPontosFidelidade,
    )
    return _serializar_pedido(pedido)


@router.get("/pedidos", summary="Listar pedidos com paginacao e filtro por canalPedido e status")
def listar_pedidos(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    canalPedido: CanalPedido | None = Query(None, description="Filtrar por canal de origem (APP, TOTEM, BALCAO, PICKUP, WEB)"),
    status_filtro: StatusPedido | None = Query(None, alias="status"),
    unidadeId: int | None = Query(None, ge=1),
    db: Session = Depends(get_db),
    usuario: UsuarioModel = Depends(obter_usuario_atual),
):
    pedidos, total = pedido_service.listar_pedidos(
        db=db,
        usuario=usuario,
        page=page,
        limit=limit,
        canal_pedido=canalPedido,
        status=status_filtro,
        unidade_id=unidadeId,
    )
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "items": [_serializar_pedido(p) for p in pedidos],
    }


@router.get("/pedidos/{pedido_id}", response_model=PedidoOut, summary="Consultar detalhes de um pedido por ID")
def obter_pedido(
    pedido_id: int,
    db: Session = Depends(get_db),
    usuario: UsuarioModel = Depends(obter_usuario_atual),
):
    pedido = pedido_service.obter_pedido_por_id(db=db, pedido_id=pedido_id, usuario=usuario)
    return _serializar_pedido(pedido)


@router.patch("/pedidos/{pedido_id}/status", response_model=PedidoOut, summary="Atualizar status operacional do pedido (COZINHA/ATENDENTE/GERENTE)")
def atualizar_status(
    pedido_id: int,
    payload: AtualizarStatusPedidoIn,
    db: Session = Depends(get_db),
    usuario: UsuarioModel = Depends(
        exigir_perfis(PerfilUsuario.COZINHA, PerfilUsuario.ATENDENTE, PerfilUsuario.GERENTE, PerfilUsuario.MATRIZ)
    ),
):
    pedido = pedido_service.atualizar_status_pedido(
        db=db,
        pedido_id=pedido_id,
        novo_status=payload.status,
        usuario=usuario,
    )
    return _serializar_pedido(pedido)


@router.post("/pedidos/{pedido_id}/cancelar", response_model=PedidoOut, summary="Cancelar pedido e estornar estoque automaticamente")
def cancelar_pedido(
    pedido_id: int,
    payload: CancelarPedidoIn,
    db: Session = Depends(get_db),
    usuario: UsuarioModel = Depends(obter_usuario_atual),
):
    pedido = pedido_service.cancelar_pedido(
        db=db,
        pedido_id=pedido_id,
        motivo=payload.motivo,
        usuario=usuario,
    )
    return _serializar_pedido(pedido)


@router.post("/pagamentos/mock", response_model=PagamentoMockOut, summary="Simular pagamento em gateway externo desacoplado com idempotencia")
def processar_pagamento_mock(
    payload: PagamentoMockIn,
    db: Session = Depends(get_db),
    usuario: UsuarioModel = Depends(obter_usuario_atual),
):
    pagamento, pedido, reaproveitado = pagamento_service.processar_pagamento_mock(
        db=db,
        pedido_id=payload.pedidoId,
        idempotency_key=payload.idempotencyKey,
        simular_resultado=payload.simularResultado,
        usuario=usuario,
    )

    if reaproveitado:
        mensagem = "Transacao recuperada por idempotencia (nenhuma cobranca duplicada foi gerada)."
    elif pagamento.status == StatusPagamento.APROVADO.value:
        mensagem = "Pagamento aprovado pelo gateway mock. Pedido encaminhado para EM_PREPARO."
    else:
        mensagem = "Pagamento recusado pelo gateway mock. Pedido permanece em AGUARDANDO_PAGAMENTO."

    return PagamentoMockOut(
        pagamentoId=pagamento.id,
        pedidoId=pagamento.pedido_id,
        idempotencyKey=pagamento.idempotency_key,
        idempotenteReaproveitado=reaproveitado,
        provedor=pagamento.provedor,
        statusPagamento=pagamento.status,
        pedidoStatus=pedido.status,
        valor=float(pagamento.valor),
        codigoTransacao=pagamento.codigo_transacao,
        mensagem=mensagem,
        gatewayPayload=json.loads(pagamento.payload_retorno),
        processadoEm=pagamento.processado_em,
    )