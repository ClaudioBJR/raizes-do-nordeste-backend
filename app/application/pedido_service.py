from decimal import Decimal, ROUND_HALF_UP
from sqlalchemy.orm import Session, joinedload
from app.application.audit_service import registrar_auditoria
from app.domain.enums import (
    CanalPedido,
    FormaPagamento,
    NivelFidelidade,
    PerfilUsuario,
    StatusPedido,
    TipoMovimentacaoEstoque,
    TipoMovimentacaoFidelidade,
    TipoOperacaoUnidade,
)
from app.domain.exceptions import (
    ConflitoNegocioError,
    RecursoNaoEncontradoError,
    SemPermissaoError,
    ValidacaoDominioError,
)
from app.domain.rules import (
    calcular_desconto_resgate_pontos,
    percentual_desconto_nivel,
    validar_transicao_status,
)
from app.infrastructure.models import (
    EstoqueUnidadeModel,
    FidelidadeContaModel,
    FidelidadeMovimentacaoModel,
    MovimentacaoEstoqueModel,
    PedidoItemModel,
    PedidoModel,
    ProdutoModel,
    UnidadeModel,
    UsuarioModel,
)


def criar_pedido(
    db: Session,
    usuario: UsuarioModel,
    unidade_id: int,
    canal_pedido: CanalPedido,
    forma_pagamento: FormaPagamento,
    itens_payload: list[dict],
    usar_pontos_fidelidade: int = 0,
) -> PedidoModel:
    unidade = (
        db.query(UnidadeModel)
        .filter(UnidadeModel.id == unidade_id, UnidadeModel.ativo.is_(True))
        .first()
    )
    if not unidade:
        raise RecursoNaoEncontradoError(
            message="Unidade nao encontrada ou inativa.",
            details=[{"field": "unidadeId", "issue": f"ID {unidade_id} inexistente"}],
        )

    pedido = PedidoModel(
        cliente_id=usuario.id,
        unidade_id=unidade.id,
        canal_pedido=canal_pedido.value,
        status=StatusPedido.AGUARDANDO_PAGAMENTO.value,
        forma_pagamento=forma_pagamento.value,
    )
    db.add(pedido)
    db.flush()

    subtotal_geral = Decimal("0.00")
    erros_estoque: list[dict] = []
    estoques_para_debitar: list[tuple[EstoqueUnidadeModel, ProdutoModel, int]] = []

    for idx, item in enumerate(itens_payload):
        produto_id = item["produto_id"]
        qtd = item["quantidade"]

        produto = (
            db.query(ProdutoModel)
            .filter(ProdutoModel.id == produto_id, ProdutoModel.ativo.is_(True))
            .first()
        )
        if not produto:
            db.rollback()
            raise RecursoNaoEncontradoError(
                message="Produto nao encontrado ou inativo.",
                details=[{"field": f"itens[{idx}].produtoId", "issue": f"Produto {produto_id} inexistente"}],
            )

        if (
            unidade.tipo_operacao == TipoOperacaoUnidade.FORMATO_REDUZIDO.value
            and produto.requer_cozinha_completa
        ):
            db.rollback()
            raise ConflitoNegocioError(
                error_code="PRODUTO_INDISPONIVEL_NA_UNIDADE",
                message="Produto exige cozinha completa e nao esta disponivel nesta unidade.",
                details=[{"field": f"itens[{idx}].produtoId", "issue": produto.nome}],
            )

        estoque = (
            db.query(EstoqueUnidadeModel)
            .filter(
                EstoqueUnidadeModel.unidade_id == unidade.id,
                EstoqueUnidadeModel.produto_id == produto.id,
                EstoqueUnidadeModel.disponivel_unidade.is_(True),
            )
            .first()
        )
        disponivel = estoque.quantidade if estoque else 0
        if not estoque or disponivel < qtd:
            erros_estoque.append(
                {"field": f"itens[{idx}].quantidade", "issue": f"Disponivel: {disponivel}"}
            )
            continue

        estoques_para_debitar.append((estoque, produto, qtd))

    if erros_estoque:
        db.rollback()
        raise ConflitoNegocioError(
            error_code="ESTOQUE_INSUFICIENTE",
            message="Nao ha quantidade suficiente para um ou mais itens.",
            details=erros_estoque,
        )

    # Verifica soma total caso o mesmo produto tenha sido enviado em duas linhas
    demanda_por_estoque: dict[int, int] = {}
    for estoque, _produto, qtd in estoques_para_debitar:
        demanda_por_estoque[estoque.id] = demanda_por_estoque.get(estoque.id, 0) + qtd
        if demanda_por_estoque[estoque.id] > estoque.quantidade:
            db.rollback()
            raise ConflitoNegocioError(
                error_code="ESTOQUE_INSUFICIENTE",
                message="Nao ha quantidade suficiente para um ou mais itens.",
                details=[{"field": "itens", "issue": f"Disponivel: {estoque.quantidade}"}],
            )

    for estoque, produto, qtd in estoques_para_debitar:
        preco_unit = Decimal(str(produto.preco_base)).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        sub_item = (preco_unit * qtd).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
        subtotal_geral += sub_item

        db.add(
            PedidoItemModel(
                pedido_id=pedido.id,
                produto_id=produto.id,
                quantidade=qtd,
                preco_unitario=preco_unit,
                subtotal=sub_item,
            )
        )
        estoque.quantidade -= qtd
        db.add(
            MovimentacaoEstoqueModel(
                estoque_id=estoque.id,
                pedido_id=pedido.id,
                tipo=TipoMovimentacaoEstoque.SAIDA.value,
                quantidade=qtd,
                motivo=f"Reserva de estoque - Pedido #{pedido.id}",
            )
        )

    # Desconto progressivo por nivel + eventual resgate de pontos (somente com consentimento)
    desconto_total = Decimal("0.00")
    conta_fidelidade = None
    if usuario.consentimento_fidelidade:
        conta_fidelidade = (
            db.query(FidelidadeContaModel)
            .filter(FidelidadeContaModel.usuario_id == usuario.id)
            .first()
        )
        if conta_fidelidade:
            perc = percentual_desconto_nivel(NivelFidelidade(conta_fidelidade.nivel))
            desconto_total += (subtotal_geral * perc).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    if usar_pontos_fidelidade > 0:
        if not usuario.consentimento_fidelidade or not conta_fidelidade:
            db.rollback()
            raise ValidacaoDominioError(
                message="Cliente nao possui consentimento ativo no programa de fidelidade.",
                details=[{"field": "usarPontosFidelidade", "issue": "Consentimento ausente"}],
            )
        if conta_fidelidade.saldo_pontos < usar_pontos_fidelidade:
            db.rollback()
            raise ConflitoNegocioError(
                error_code="PONTOS_INSUFICIENTES",
                message="Saldo de pontos de fidelidade insuficiente.",
                details=[{"field": "usarPontosFidelidade", "issue": f"Disponivel: {conta_fidelidade.saldo_pontos}"}],
            )
        desconto_pontos = calcular_desconto_resgate_pontos(usar_pontos_fidelidade)
        desconto_total += desconto_pontos
        conta_fidelidade.saldo_pontos -= usar_pontos_fidelidade
        db.add(
            FidelidadeMovimentacaoModel(
                conta_id=conta_fidelidade.id,
                pedido_id=pedido.id,
                tipo=TipoMovimentacaoFidelidade.RESGATE.value,
                pontos=usar_pontos_fidelidade,
            )
        )

    if desconto_total > subtotal_geral:
        desconto_total = subtotal_geral

    pedido.subtotal = subtotal_geral
    pedido.desconto_fidelidade = desconto_total
    pedido.valor_total = (subtotal_geral - desconto_total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)

    registrar_auditoria(
        db=db,
        acao="PEDIDO_CRIADO",
        entidade="PEDIDOS",
        entidade_id=pedido.id,
        usuario_id=usuario.id,
        detalhes={
            "unidadeId": unidade.id,
            "canalPedido": pedido.canal_pedido,
            "valorTotal": str(pedido.valor_total),
            "descontoFidelidade": str(pedido.desconto_fidelidade),
        },
    )

    db.commit()
    return obter_pedido_por_id(db, pedido.id, usuario)


def listar_pedidos(
    db: Session,
    usuario: UsuarioModel,
    page: int = 1,
    limit: int = 10,
    canal_pedido: CanalPedido | None = None,
    status: StatusPedido | None = None,
    unidade_id: int | None = None,
) -> tuple[list[PedidoModel], int]:
    query = db.query(PedidoModel).options(joinedload(PedidoModel.itens))

    if usuario.perfil == PerfilUsuario.CLIENTE.value:
        query = query.filter(PedidoModel.cliente_id == usuario.id)
    if canal_pedido:
        query = query.filter(PedidoModel.canal_pedido == canal_pedido.value)
    if status:
        query = query.filter(PedidoModel.status == status.value)
    if unidade_id:
        query = query.filter(PedidoModel.unidade_id == unidade_id)

    total = query.count()
    itens = (
        query.order_by(PedidoModel.id.desc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return itens, total


def obter_pedido_por_id(db: Session, pedido_id: int, usuario: UsuarioModel) -> PedidoModel:
    pedido = (
        db.query(PedidoModel)
        .options(joinedload(PedidoModel.itens), joinedload(PedidoModel.pagamentos))
        .filter(PedidoModel.id == pedido_id)
        .first()
    )
    if not pedido:
        raise RecursoNaoEncontradoError(
            message="Pedido nao encontrado.",
            details=[{"field": "pedidoId", "issue": f"ID {pedido_id} inexistente"}],
        )

    if usuario.perfil == PerfilUsuario.CLIENTE.value and pedido.cliente_id != usuario.id:
        raise SemPermissaoError("Voce nao tem permissao para acessar pedidos de outro cliente.")

    return pedido


def atualizar_status_pedido(
    db: Session,
    pedido_id: int,
    novo_status: StatusPedido,
    usuario: UsuarioModel,
) -> PedidoModel:
    pedido = (
        db.query(PedidoModel)
        .options(joinedload(PedidoModel.itens))
        .filter(PedidoModel.id == pedido_id)
        .first()
    )
    if not pedido:
        raise RecursoNaoEncontradoError("Pedido nao encontrado.")

    status_anterior = StatusPedido(pedido.status)
    validar_transicao_status(status_anterior, novo_status)

    pedido.status = novo_status.value

    if novo_status == StatusPedido.CANCELADO:
        _estornar_estoque_pedido(db, pedido)

    registrar_auditoria(
        db=db,
        acao="PEDIDO_STATUS_ATUALIZADO",
        entidade="PEDIDOS",
        entidade_id=pedido.id,
        usuario_id=usuario.id,
        detalhes={"statusAnterior": status_anterior.value, "statusNovo": novo_status.value},
    )
    db.commit()
    db.refresh(pedido)
    return pedido


def cancelar_pedido(db: Session, pedido_id: int, motivo: str, usuario: UsuarioModel) -> PedidoModel:
    pedido = obter_pedido_por_id(db, pedido_id, usuario)
    status_anterior = StatusPedido(pedido.status)
    validar_transicao_status(status_anterior, StatusPedido.CANCELADO)

    pedido.status = StatusPedido.CANCELADO.value
    _estornar_estoque_pedido(db, pedido)

    registrar_auditoria(
        db=db,
        acao="PEDIDO_CANCELADO",
        entidade="PEDIDOS",
        entidade_id=pedido.id,
        usuario_id=usuario.id,
        detalhes={"statusAnterior": status_anterior.value, "motivo": motivo},
    )
    db.commit()
    db.refresh(pedido)
    return pedido


def _estornar_estoque_pedido(db: Session, pedido: PedidoModel) -> None:
    for item in pedido.itens:
        estoque = (
            db.query(EstoqueUnidadeModel)
            .filter(
                EstoqueUnidadeModel.unidade_id == pedido.unidade_id,
                EstoqueUnidadeModel.produto_id == item.produto_id,
            )
            .first()
        )
        if estoque:
            estoque.quantidade += item.quantidade
            db.add(
                MovimentacaoEstoqueModel(
                    estoque_id=estoque.id,
                    pedido_id=pedido.id,
                    tipo=TipoMovimentacaoEstoque.ESTORNO.value,
                    quantidade=item.quantidade,
                    motivo=f"Estorno automatico - Cancelamento Pedido #{pedido.id}",
                )
            )