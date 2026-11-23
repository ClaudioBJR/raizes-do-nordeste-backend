from decimal import Decimal
from sqlalchemy.orm import Session
from app.application.audit_service import registrar_auditoria
from app.domain.enums import (
    PerfilUsuario,
    StatusPagamento,
    StatusPedido,
    TipoMovimentacaoFidelidade,
)
from app.domain.exceptions import (
    ConflitoNegocioError,
    RecursoNaoEncontradoError,
    SemPermissaoError,
)
from app.domain.rules import calcular_pontos_fidelidade, determinar_nivel_fidelidade
from app.infrastructure.models import (
    FidelidadeContaModel,
    FidelidadeMovimentacaoModel,
    PagamentoModel,
    PedidoModel,
    UsuarioModel,
)
from app.infrastructure.payment_gateway import MockPaymentGateway


def processar_pagamento_mock(
    db: Session,
    pedido_id: int,
    idempotency_key: str,
    simular_resultado: StatusPagamento,
    usuario: UsuarioModel,
) -> tuple[PagamentoModel, PedidoModel, bool]:
    # 1. Controle de idempotencia: retentativa com mesma chave retorna transacao ja gravada
    existente = (
        db.query(PagamentoModel)
        .filter(PagamentoModel.idempotency_key == idempotency_key)
        .first()
    )
    if existente:
        if existente.pedido_id != pedido_id:
            raise ConflitoNegocioError(
                error_code="IDEMPOTENCY_KEY_CONFLITO",
                message="Esta idempotencyKey ja foi utilizada para outro pedido.",
                details=[{"field": "idempotencyKey", "issue": "Chave vinculada a outro pedido"}],
            )
        pedido_existente = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
        return existente, pedido_existente, True

    pedido = db.query(PedidoModel).filter(PedidoModel.id == pedido_id).first()
    if not pedido:
        raise RecursoNaoEncontradoError(
            message="Pedido nao encontrado para pagamento.",
            details=[{"field": "pedidoId", "issue": f"ID {pedido_id} inexistente"}],
        )

    if usuario.perfil == PerfilUsuario.CLIENTE.value and pedido.cliente_id != usuario.id:
        raise SemPermissaoError("Voce nao pode pagar um pedido de outro cliente.")

    if pedido.status != StatusPedido.AGUARDANDO_PAGAMENTO.value:
        raise ConflitoNegocioError(
            error_code="PEDIDO_NAO_AGUARDANDO_PAGAMENTO",
            message=f"Pedido esta no status {pedido.status} e nao aceita novo pagamento.",
            details=[{"field": "status", "issue": pedido.status}],
        )

    gateway = MockPaymentGateway()
    retorno = gateway.processar_cobranca(
        pedido_id=pedido.id,
        valor=Decimal(str(pedido.valor_total)),
        forma_pagamento=pedido.forma_pagamento,
        simular_resultado=simular_resultado,
    )

    pagamento = PagamentoModel(
        pedido_id=pedido.id,
        idempotency_key=idempotency_key,
        provedor=retorno["provedor"],
        status=retorno["status"],
        valor=pedido.valor_total,
        codigo_transacao=retorno["codigo_transacao"],
        payload_retorno=retorno["payload_retorno"],
    )
    db.add(pagamento)
    db.flush()

    pontos_creditados = 0
    if simular_resultado == StatusPagamento.APROVADO:
        pedido.status = StatusPedido.EM_PREPARO.value
        cliente = db.query(UsuarioModel).filter(UsuarioModel.id == pedido.cliente_id).first()

        if cliente and cliente.consentimento_fidelidade and not cliente.anonimizado:
            conta = (
                db.query(FidelidadeContaModel)
                .filter(FidelidadeContaModel.usuario_id == cliente.id)
                .first()
            )
            if not conta:
                conta = FidelidadeContaModel(
                    usuario_id=cliente.id,
                    saldo_pontos=0,
                    total_pedidos_pagos=0,
                    nivel="BRONZE",
                )
                db.add(conta)
                db.flush()

            pontos_creditados = calcular_pontos_fidelidade(Decimal(str(pedido.valor_total)))
            conta.saldo_pontos += pontos_creditados
            conta.total_pedidos_pagos += 1
            conta.nivel = determinar_nivel_fidelidade(conta.total_pedidos_pagos).value

            if pontos_creditados > 0:
                db.add(
                    FidelidadeMovimentacaoModel(
                        conta_id=conta.id,
                        pedido_id=pedido.id,
                        tipo=TipoMovimentacaoFidelidade.CREDITO.value,
                        pontos=pontos_creditados,
                    )
                )

        registrar_auditoria(
            db=db,
            acao="PAGAMENTO_APROVADO",
            entidade="PAGAMENTOS",
            entidade_id=pagamento.id,
            usuario_id=usuario.id,
            detalhes={
                "pedidoId": pedido.id,
                "novoStatusPedido": pedido.status,
                "codigoTransacao": pagamento.codigo_transacao,
                "pontosCreditados": pontos_creditados,
            },
        )
    else:
        registrar_auditoria(
            db=db,
            acao="PAGAMENTO_RECUSADO",
            entidade="PAGAMENTOS",
            entidade_id=pagamento.id,
            usuario_id=usuario.id,
            detalhes={
                "pedidoId": pedido.id,
                "statusPedidoMantido": pedido.status,
                "codigoTransacao": pagamento.codigo_transacao,
            },
        )

    db.commit()
    db.refresh(pagamento)
    db.refresh(pedido)
    return pagamento, pedido, False