from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session
from app.api.dependencies import exigir_perfis
from app.api.schemas import (
    CardapioItemOut,
    EstoqueOut,
    MovimentacaoEstoqueIn,
    ProdutoIn,
    ProdutoOut,
    UnidadeIn,
    UnidadeOut,
)
from app.application import catalogo_service
from app.domain.enums import CategoriaProduto, PerfilUsuario, RegiaoBrasil, TipoOperacaoUnidade
from app.infrastructure.database import get_db
from app.infrastructure.models import UsuarioModel

router = APIRouter(tags=["Unidades, Produtos e Estoque"])


@router.get("/unidades", summary="Listar unidades da rede com paginacao e filtros")
def listar_unidades(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    regiao: RegiaoBrasil | None = Query(None),
    tipoOperacao: TipoOperacaoUnidade | None = Query(None),
    db: Session = Depends(get_db),
):
    unidades, total = catalogo_service.listar_unidades(
        db=db, page=page, limit=limit, regiao=regiao, tipo_operacao=tipoOperacao
    )
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "items": [
            UnidadeOut(
                id=u.id,
                nome=u.nome,
                codigo=u.codigo,
                cidade=u.cidade,
                regiao=u.regiao,
                tipoOperacao=u.tipo_operacao,
                horarioFuncionamento=u.horario_funcionamento,
                ativo=u.ativo,
            )
            for u in unidades
        ],
    }


@router.post("/unidades", response_model=UnidadeOut, status_code=status.HTTP_201_CREATED, summary="Cadastrar nova unidade (GERENTE/MATRIZ)")
def criar_unidade(
    payload: UnidadeIn,
    db: Session = Depends(get_db),
    usuario: UsuarioModel = Depends(exigir_perfis(PerfilUsuario.GERENTE, PerfilUsuario.MATRIZ)),
):
    u = catalogo_service.criar_unidade(
        db=db,
        nome=payload.nome,
        codigo=payload.codigo,
        cidade=payload.cidade,
        regiao=payload.regiao,
        tipo_operacao=payload.tipoOperacao,
        horario_funcionamento=payload.horarioFuncionamento,
        usuario=usuario,
    )
    return UnidadeOut(
        id=u.id,
        nome=u.nome,
        codigo=u.codigo,
        cidade=u.cidade,
        regiao=u.regiao,
        tipoOperacao=u.tipo_operacao,
        horarioFuncionamento=u.horario_funcionamento,
        ativo=u.ativo,
    )


@router.get("/unidades/{unidade_id}/cardapio", summary="Consultar cardapio e disponibilidade por unidade")
def consultar_cardapio(
    unidade_id: int,
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    apenasComEstoque: bool = Query(False),
    db: Session = Depends(get_db),
):
    unidade, estoques, total = catalogo_service.consultar_cardapio_unidade(
        db=db,
        unidade_id=unidade_id,
        page=page,
        limit=limit,
        apenas_com_estoque=apenasComEstoque,
    )
    return {
        "unidade": {
            "id": unidade.id,
            "codigo": unidade.codigo,
            "nome": unidade.nome,
            "tipoOperacao": unidade.tipo_operacao,
            "horarioFuncionamento": unidade.horario_funcionamento,
        },
        "page": page,
        "limit": limit,
        "total": total,
        "items": [
            CardapioItemOut(
                produtoId=e.produto.id,
                nome=e.produto.nome,
                descricao=e.produto.descricao,
                categoria=e.produto.categoria,
                precoBase=float(e.produto.preco_base),
                sazonal=e.produto.sazonal,
                periodoSazonal=e.produto.periodo_sazonal,
                requerCozinhaCompleta=e.produto.requer_cozinha_completa,
                quantidadeEstoque=e.quantidade,
                disponivel=e.quantidade > 0 and e.disponivel_unidade,
            )
            for e in estoques
        ],
    }


@router.get("/produtos", summary="Listar catalogo mestre de produtos da rede")
def listar_produtos(
    page: int = Query(1, ge=1),
    limit: int = Query(10, ge=1, le=50),
    categoria: CategoriaProduto | None = Query(None),
    sazonal: bool | None = Query(None),
    db: Session = Depends(get_db),
):
    produtos, total = catalogo_service.listar_produtos(
        db=db, page=page, limit=limit, categoria=categoria, sazonal=sazonal
    )
    return {
        "page": page,
        "limit": limit,
        "total": total,
        "items": [
            ProdutoOut(
                id=p.id,
                nome=p.nome,
                descricao=p.descricao,
                categoria=p.categoria,
                precoBase=float(p.preco_base),
                sazonal=p.sazonal,
                periodoSazonal=p.periodo_sazonal,
                requerCozinhaCompleta=p.requer_cozinha_completa,
                ativo=p.ativo,
            )
            for p in produtos
        ],
    }


@router.post("/produtos", response_model=ProdutoOut, status_code=status.HTTP_201_CREATED, summary="Cadastrar produto no catalogo mestre (GERENTE/MATRIZ)")
def criar_produto(
    payload: ProdutoIn,
    db: Session = Depends(get_db),
    usuario: UsuarioModel = Depends(exigir_perfis(PerfilUsuario.GERENTE, PerfilUsuario.MATRIZ)),
):
    p = catalogo_service.criar_produto(
        db=db,
        nome=payload.nome,
        descricao=payload.descricao,
        categoria=payload.categoria,
        preco_base=payload.precoBase,
        sazonal=payload.sazonal,
        periodo_sazonal=payload.periodoSazonal,
        requer_cozinha_completa=payload.requerCozinhaCompleta,
        usuario=usuario,
    )
    return ProdutoOut(
        id=p.id,
        nome=p.nome,
        descricao=p.descricao,
        categoria=p.categoria,
        precoBase=float(p.preco_base),
        sazonal=p.sazonal,
        periodoSazonal=p.periodo_sazonal,
        requerCozinhaCompleta=p.requer_cozinha_completa,
        ativo=p.ativo,
    )


@router.post("/estoque/movimentacoes", response_model=EstoqueOut, summary="Registrar entrada, saida ou ajuste de estoque local (GERENTE/MATRIZ/ATENDENTE)")
def movimentar_estoque(
    payload: MovimentacaoEstoqueIn,
    db: Session = Depends(get_db),
    usuario: UsuarioModel = Depends(
        exigir_perfis(PerfilUsuario.GERENTE, PerfilUsuario.MATRIZ, PerfilUsuario.ATENDENTE)
    ),
):
    e = catalogo_service.movimentar_estoque(
        db=db,
        unidade_id=payload.unidadeId,
        produto_id=payload.produtoId,
        tipo=payload.tipo,
        quantidade=payload.quantidade,
        motivo=payload.motivo,
        usuario=usuario,
    )
    return EstoqueOut(
        id=e.id,
        unidadeId=e.unidade_id,
        produtoId=e.produto_id,
        quantidade=e.quantidade,
        disponivelUnidade=e.disponivel_unidade,
        atualizadoEm=e.atualizado_em,
    )