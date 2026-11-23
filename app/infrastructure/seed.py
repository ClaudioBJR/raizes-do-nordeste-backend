from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy.orm import Session
from app.infrastructure.database import SessionLocal
from app.infrastructure.models import (
    EstoqueUnidadeModel,
    FidelidadeContaModel,
    MovimentacaoEstoqueModel,
    ProdutoModel,
    UnidadeModel,
    UsuarioModel,
)
from app.infrastructure.security import gerar_hash_senha


def executar_seed(db: Session) -> dict[str, int]:
    if db.query(UsuarioModel).count() > 0:
        return {"status": 0, "mensagem": "Base ja populada"}

    agora = datetime.now(timezone.utc)
    senha_padrao = gerar_hash_senha("Senha@123")

    usuarios = [
        UsuarioModel(
            nome="Diretoria Matriz Raizes",
            email="matriz@raizesdonordeste.com.br",
            senha_hash=senha_padrao,
            perfil="MATRIZ",
            consentimento_lgpd=True,
            consentimento_fidelidade=False,
            consentimento_em=agora,
        ),
        UsuarioModel(
            nome="Francisca Gerente Recife",
            email="gerente@raizesdonordeste.com.br",
            senha_hash=senha_padrao,
            perfil="GERENTE",
            consentimento_lgpd=True,
            consentimento_fidelidade=False,
            consentimento_em=agora,
        ),
        UsuarioModel(
            nome="Joao Cozinha Recife",
            email="cozinha@raizesdonordeste.com.br",
            senha_hash=senha_padrao,
            perfil="COZINHA",
            consentimento_lgpd=True,
            consentimento_fidelidade=False,
            consentimento_em=agora,
        ),
        UsuarioModel(
            nome="Carla Atendente Balcao",
            email="atendente@raizesdonordeste.com.br",
            senha_hash=senha_padrao,
            perfil="ATENDENTE",
            consentimento_lgpd=True,
            consentimento_fidelidade=False,
            consentimento_em=agora,
        ),
        UsuarioModel(
            nome="Maria Cliente Fiel",
            email="cliente@raizesdonordeste.com.br",
            senha_hash=senha_padrao,
            perfil="CLIENTE",
            faixa_etaria="25-34",
            consentimento_lgpd=True,
            consentimento_fidelidade=True,
            consentimento_em=agora,
        ),
    ]
    db.add_all(usuarios)
    db.flush()

    cliente_fiel = usuarios[-1]
    db.add(
        FidelidadeContaModel(
            usuario_id=cliente_fiel.id,
            saldo_pontos=50,
            total_pedidos_pagos=2,
            nivel="BRONZE",
        )
    )

    unidades = [
        UnidadeModel(
            nome="Recife - Boa Viagem (Unidade 1)",
            codigo="REC-01",
            cidade="Recife",
            regiao="NORDESTE",
            tipo_operacao="COZINHA_COMPLETA",
            horario_funcionamento="06:30-22:00",
        ),
        UnidadeModel(
            nome="Caruaru - Centro",
            codigo="CAR-01",
            cidade="Caruaru",
            regiao="NORDESTE",
            tipo_operacao="COZINHA_COMPLETA",
            horario_funcionamento="08:00-21:00",
        ),
        UnidadeModel(
            nome="Sao Paulo - Paulista Express",
            codigo="SPO-01",
            cidade="Sao Paulo",
            regiao="SUDESTE",
            tipo_operacao="FORMATO_REDUZIDO",
            horario_funcionamento="07:00-20:00",
        ),
    ]
    db.add_all(unidades)
    db.flush()

    produtos = [
        ProdutoModel(
            nome="Cuscuz Recheado com Carne de Sol",
            descricao="Cuscuz de milho flocado com carne de sol na nata e queijo coalho.",
            categoria="CUSCUZ",
            preco_base=Decimal("28.90"),
            sazonal=False,
            requer_cozinha_completa=True,
        ),
        ProdutoModel(
            nome="Tapioca de Queijo Coalho e Manteiga de Garrafa",
            descricao="Goma fresca hidratada recheada com queijo coalho grelhado.",
            categoria="TAPIOCA",
            preco_base=Decimal("19.50"),
            sazonal=False,
            requer_cozinha_completa=False,
        ),
        ProdutoModel(
            nome="Bolo de Macaxeira Cremoso (Fatia)",
            descricao="Receita tradicional da Dona Francisca com coco ralado.",
            categoria="BOLOS",
            preco_base=Decimal("14.00"),
            sazonal=False,
            requer_cozinha_completa=False,
        ),
        ProdutoModel(
            nome="Cafe Passado na Hora (300ml)",
            descricao="Cafe coado no pano, graos selecionados do Nordeste.",
            categoria="BEBIDAS",
            preco_base=Decimal("8.50"),
            sazonal=False,
            requer_cozinha_completa=False,
        ),
        ProdutoModel(
            nome="Suco Regional de Caju (400ml)",
            descricao="Polpa natural de caju batida na hora.",
            categoria="BEBIDAS",
            preco_base=Decimal("12.00"),
            sazonal=False,
            requer_cozinha_completa=False,
        ),
        ProdutoModel(
            nome="Canjica Nordestina Especial (Junina)",
            descricao="Produto sazonal do periodo junino com canela.",
            categoria="SAZONAL",
            preco_base=Decimal("16.50"),
            sazonal=True,
            periodo_sazonal="JUNINO",
            requer_cozinha_completa=True,
        ),
    ]
    db.add_all(produtos)
    db.flush()

    estoques_criados = 0
    for unidade in unidades:
        for produto in produtos:
            # Unidades de formato reduzido nao servem itens que exigem cozinha completa
            if unidade.tipo_operacao == "FORMATO_REDUZIDO" and produto.requer_cozinha_completa:
                continue

            qtd_inicial = 2 if produto.sazonal else 20
            estoque = EstoqueUnidadeModel(
                unidade_id=unidade.id,
                produto_id=produto.id,
                quantidade=qtd_inicial,
                disponivel_unidade=True,
            )
            db.add(estoque)
            db.flush()
            db.add(
                MovimentacaoEstoqueModel(
                    estoque_id=estoque.id,
                    tipo="ENTRADA",
                    quantidade=qtd_inicial,
                    motivo="Carga inicial (seed)",
                )
            )
            estoques_criados += 1

    db.commit()
    return {
        "usuarios": len(usuarios),
        "unidades": len(unidades),
        "produtos": len(produtos),
        "estoques": estoques_criados,
    }


if __name__ == "__main__":
    with SessionLocal() as session:
        resumo = executar_seed(session)
        print("SEED EXECUTADO COM SUCESSO:", resumo)