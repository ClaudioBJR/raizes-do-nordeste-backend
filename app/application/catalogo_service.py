from decimal import Decimal
from sqlalchemy.orm import Session, joinedload
from app.application.audit_service import registrar_auditoria
from app.domain.enums import (
    CategoriaProduto,
    RegiaoBrasil,
    TipoMovimentacaoEstoque,
    TipoOperacaoUnidade,
)
from app.domain.exceptions import (
    ConflitoNegocioError,
    RecursoNaoEncontradoError,
)
from app.infrastructure.models import (
    EstoqueUnidadeModel,
    MovimentacaoEstoqueModel,
    ProdutoModel,
    UnidadeModel,
    UsuarioModel,
)


def listar_unidades(
    db: Session,
    page: int = 1,
    limit: int = 10,
    regiao: RegiaoBrasil | None = None,
    tipo_operacao: TipoOperacaoUnidade | None = None,
) -> tuple[list[UnidadeModel], int]:
    query = db.query(UnidadeModel).filter(UnidadeModel.ativo.is_(True))
    if regiao:
        query = query.filter(UnidadeModel.regiao == regiao.value)
    if tipo_operacao:
        query = query.filter(UnidadeModel.tipo_operacao == tipo_operacao.value)

    total = query.count()
    itens = (
        query.order_by(UnidadeModel.id.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return itens, total


def criar_unidade(
    db: Session,
    nome: str,
    codigo: str,
    cidade: str,
    regiao: RegiaoBrasil,
    tipo_operacao: TipoOperacaoUnidade,
    horario_funcionamento: str,
    usuario: UsuarioModel,
) -> UnidadeModel:
    codigo_norm = codigo.strip().upper()
    if db.query(UnidadeModel).filter(UnidadeModel.codigo == codigo_norm).first():
        raise ConflitoNegocioError(
            error_code="UNIDADE_CODIGO_DUPLICADO",
            message="Ja existe uma unidade cadastrada com este codigo.",
            details=[{"field": "codigo", "issue": codigo_norm}],
        )

    unidade = UnidadeModel(
        nome=nome.strip(),
        codigo=codigo_norm,
        cidade=cidade.strip(),
        regiao=regiao.value,
        tipo_operacao=tipo_operacao.value,
        horario_funcionamento=horario_funcionamento.strip(),
    )
    db.add(unidade)
    db.flush()

    registrar_auditoria(
        db=db,
        acao="UNIDADE_CRIADA",
        entidade="UNIDADES",
        entidade_id=unidade.id,
        usuario_id=usuario.id,
        detalhes={"codigo": unidade.codigo, "tipoOperacao": unidade.tipo_operacao},
    )
    db.commit()
    db.refresh(unidade)
    return unidade


def listar_produtos(
    db: Session,
    page: int = 1,
    limit: int = 10,
    categoria: CategoriaProduto | None = None,
    sazonal: bool | None = None,
) -> tuple[list[ProdutoModel], int]:
    query = db.query(ProdutoModel).filter(ProdutoModel.ativo.is_(True))
    if categoria:
        query = query.filter(ProdutoModel.categoria == categoria.value)
    if sazonal is not None:
        query = query.filter(ProdutoModel.sazonal.is_(sazonal))

    total = query.count()
    itens = (
        query.order_by(ProdutoModel.id.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return itens, total


def criar_produto(
    db: Session,
    nome: str,
    descricao: str,
    categoria: CategoriaProduto,
    preco_base: Decimal,
    sazonal: bool,
    periodo_sazonal: str | None,
    requer_cozinha_completa: bool,
    usuario: UsuarioModel,
) -> ProdutoModel:
    produto = ProdutoModel(
        nome=nome.strip(),
        descricao=descricao.strip(),
        categoria=categoria.value,
        preco_base=preco_base,
        sazonal=sazonal,
        periodo_sazonal=periodo_sazonal.strip().upper() if periodo_sazonal else None,
        requer_cozinha_completa=requer_cozinha_completa,
    )
    db.add(produto)
    db.flush()

    registrar_auditoria(
        db=db,
        acao="PRODUTO_CRIADO",
        entidade="PRODUTOS",
        entidade_id=produto.id,
        usuario_id=usuario.id,
        detalhes={"nome": produto.nome, "precoBase": str(produto.preco_base)},
    )
    db.commit()
    db.refresh(produto)
    return produto


def consultar_cardapio_unidade(
    db: Session,
    unidade_id: int,
    page: int = 1,
    limit: int = 10,
    apenas_com_estoque: bool = False,
) -> tuple[UnidadeModel, list[EstoqueUnidadeModel], int]:
    unidade = (
        db.query(UnidadeModel)
        .filter(UnidadeModel.id == unidade_id, UnidadeModel.ativo.is_(True))
        .first()
    )
    if not unidade:
        raise RecursoNaoEncontradoError(
            message="Unidade nao encontrada.",
            details=[{"field": "unidadeId", "issue": f"ID {unidade_id} inexistente"}],
        )

    query = (
        db.query(EstoqueUnidadeModel)
        .options(joinedload(EstoqueUnidadeModel.produto))
        .join(ProdutoModel, ProdutoModel.id == EstoqueUnidadeModel.produto_id)
        .filter(
            EstoqueUnidadeModel.unidade_id == unidade_id,
            EstoqueUnidadeModel.disponivel_unidade.is_(True),
            ProdutoModel.ativo.is_(True),
        )
    )
    if apenas_com_estoque:
        query = query.filter(EstoqueUnidadeModel.quantidade > 0)

    total = query.count()
    itens = (
        query.order_by(ProdutoModel.id.asc())
        .offset((page - 1) * limit)
        .limit(limit)
        .all()
    )
    return unidade, itens, total


def movimentar_estoque(
    db: Session,
    unidade_id: int,
    produto_id: int,
    tipo: TipoMovimentacaoEstoque,
    quantidade: int,
    motivo: str,
    usuario: UsuarioModel,
) -> EstoqueUnidadeModel:
    unidade = (
        db.query(UnidadeModel)
        .filter(UnidadeModel.id == unidade_id, UnidadeModel.ativo.is_(True))
        .first()
    )
    if not unidade:
        raise RecursoNaoEncontradoError("Unidade nao encontrada.")

    produto = (
        db.query(ProdutoModel)
        .filter(ProdutoModel.id == produto_id, ProdutoModel.ativo.is_(True))
        .first()
    )
    if not produto:
        raise RecursoNaoEncontradoError("Produto nao encontrado.")

    if (
        unidade.tipo_operacao == TipoOperacaoUnidade.FORMATO_REDUZIDO.value
        and produto.requer_cozinha_completa
    ):
        raise ConflitoNegocioError(
            error_code="UNIDADE_INCOMPATIVEL_COM_PRODUTO",
            message="Unidades de formato reduzido nao podem comercializar itens que exigem cozinha completa.",
            details=[{"field": "produtoId", "issue": f"Produto {produto.nome} exige COZINHA_COMPLETA"}],
        )

    estoque = (
        db.query(EstoqueUnidadeModel)
        .filter(
            EstoqueUnidadeModel.unidade_id == unidade_id,
            EstoqueUnidadeModel.produto_id == produto_id,
        )
        .first()
    )
    if not estoque:
        estoque = EstoqueUnidadeModel(
            unidade_id=unidade_id,
            produto_id=produto_id,
            quantidade=0,
            disponivel_unidade=True,
        )
        db.add(estoque)
        db.flush()

    saldo_anterior = estoque.quantidade

    if tipo in (TipoMovimentacaoEstoque.ENTRADA, TipoMovimentacaoEstoque.ESTORNO):
        estoque.quantidade += quantidade
    elif tipo == TipoMovimentacaoEstoque.SAIDA:
        if estoque.quantidade < quantidade:
            raise ConflitoNegocioError(
                error_code="ESTOQUE_INSUFICIENTE",
                message="Saldo insuficiente para realizar a saida de estoque.",
                details=[{"field": "quantidade", "issue": f"Disponivel: {estoque.quantidade}"}],
            )
        estoque.quantidade -= quantidade
    elif tipo == TipoMovimentacaoEstoque.AJUSTE:
        estoque.quantidade = quantidade

    db.add(
        MovimentacaoEstoqueModel(
            estoque_id=estoque.id,
            tipo=tipo.value,
            quantidade=quantidade,
            motivo=motivo.strip(),
        )
    )

    registrar_auditoria(
        db=db,
        acao=f"ESTOQUE_{tipo.value}",
        entidade="ESTOQUE_UNIDADE",
        entidade_id=estoque.id,
        usuario_id=usuario.id,
        detalhes={
            "unidadeId": unidade_id,
            "produtoId": produto_id,
            "saldoAnterior": saldo_anterior,
            "saldoNovo": estoque.quantidade,
            "motivo": motivo,
        },
    )
    db.commit()
    db.refresh(estoque)
    return estoque