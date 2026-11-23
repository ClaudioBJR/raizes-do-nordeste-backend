import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, event
from sqlalchemy.orm import sessionmaker
from sqlalchemy.pool import StaticPool

from app.infrastructure.database import Base, get_db
from app.infrastructure.seed import executar_seed
from app.main import app


@pytest.fixture()
def client():
    engine = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
        future=True,
    )

    @event.listens_for(engine, "connect")
    def _enable_fk(dbapi_connection, _connection_record):
        cursor = dbapi_connection.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, future=True)
    Base.metadata.create_all(bind=engine)

    with TestingSessionLocal() as db:
        executar_seed(db)

    def _override_get_db():
        db = TestingSessionLocal()
        try:
            yield db
        finally:
            db.close()

    app.dependency_overrides[get_db] = _override_get_db
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def _obter_token(client: TestClient, email: str, senha: str = "Senha@123") -> str:
    resp = client.post("/auth/login", json={"email": email, "senha": senha})
    assert resp.status_code == 200
    return resp.json()["accessToken"]


def _headers(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


# T01 - Login valido (Positivo)
def test_t01_login_valido(client: TestClient):
    resp = client.post(
        "/auth/login",
        json={"email": "cliente@raizesdonordeste.com.br", "senha": "Senha@123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert "accessToken" in body
    assert body["tokenType"] == "Bearer"
    assert body["user"]["perfil"] == "CLIENTE"
    assert "senha_hash" not in body["user"]


# T02 - Acesso sem token retorna 401 com erro padronizado (Negativo)
def test_t02_acesso_sem_token_retorna_401(client: TestClient):
    resp = client.get("/pedidos")
    assert resp.status_code == 401
    body = resp.json()
    assert body["error"] == "NAO_AUTENTICADO"
    assert body["path"] == "/pedidos"
    assert "requestId" in body


# T03 - Acesso com perfil sem permissao retorna 403 (Negativo)
def test_t03_acesso_sem_permissao_retorna_403(client: TestClient):
    token_cliente = _obter_token(client, "cliente@raizesdonordeste.com.br")
    resp = client.get("/relatorios/matriz", headers=_headers(token_cliente))
    assert resp.status_code == 403
    assert resp.json()["error"] == "SEM_PERMISSAO"


# T04 - Consultar cardapio por unidade com paginacao (Positivo)
def test_t04_consultar_cardapio_unidade(client: TestClient):
    resp = client.get("/unidades/1/cardapio?page=1&limit=10")
    assert resp.status_code == 200
    body = resp.json()
    assert body["unidade"]["codigo"] == "REC-01"
    assert body["total"] == 6


# T05 - Validacao de dados: canalPedido ausente ou invalido retorna 422 (Negativo)
def test_t05_pedido_sem_canal_retorna_422(client: TestClient):
    token_cliente = _obter_token(client, "cliente@raizesdonordeste.com.br")
    resp = client.post(
        "/pedidos",
        headers=_headers(token_cliente),
        json={
            "unidadeId": 1,
            "itens": [{"produtoId": 1, "quantidade": 1}],
            "formaPagamento": "MOCK",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "ERRO_VALIDACAO"


# T06 - Validacao de dados: quantidade negativa retorna 422 (Negativo)
def test_t06_pedido_quantidade_invalida_retorna_422(client: TestClient):
    token_cliente = _obter_token(client, "cliente@raizesdonordeste.com.br")
    resp = client.post(
        "/pedidos",
        headers=_headers(token_cliente),
        json={
            "unidadeId": 1,
            "canalPedido": "APP",
            "itens": [{"produtoId": 1, "quantidade": -2}],
            "formaPagamento": "MOCK",
        },
    )
    assert resp.status_code == 422
    assert resp.json()["error"] == "ERRO_VALIDACAO"


# T07 - Produto inexistente retorna 404 (Negativo)
def test_t07_pedido_produto_inexistente_retorna_404(client: TestClient):
    token_cliente = _obter_token(client, "cliente@raizesdonordeste.com.br")
    resp = client.post(
        "/pedidos",
        headers=_headers(token_cliente),
        json={
            "unidadeId": 1,
            "canalPedido": "TOTEM",
            "itens": [{"produtoId": 999, "quantidade": 1}],
            "formaPagamento": "MOCK",
        },
    )
    assert resp.status_code == 404
    assert resp.json()["error"] == "RECURSO_NAO_ENCONTRADO"


# T08 - Estoque insuficiente retorna 409 (Negativo)
def test_t08_pedido_estoque_insuficiente_retorna_409(client: TestClient):
    token_cliente = _obter_token(client, "cliente@raizesdonordeste.com.br")
    # Produto 6 (Canjica Junina) tem apenas 2 unidades em estoque no seed
    resp = client.post(
        "/pedidos",
        headers=_headers(token_cliente),
        json={
            "unidadeId": 1,
            "canalPedido": "TOTEM",
            "itens": [{"produtoId": 6, "quantidade": 50}],
            "formaPagamento": "MOCK",
        },
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "ESTOQUE_INSUFICIENTE"


# T09 - Fluxo critico completo: Pedido Multicanal + Pagamento Recusado + Pagamento Aprovado + Idempotencia + Status + Fidelidade + Auditoria (Positivo)
def test_t09_fluxo_critico_completo_e_auditoria(client: TestClient):
    token_cliente = _obter_token(client, "cliente@raizesdonordeste.com.br")
    token_cozinha = _obter_token(client, "cozinha@raizesdonordeste.com.br")
    token_matriz = _obter_token(client, "matriz@raizesdonordeste.com.br")

    # 1. Criar pedido no canal TOTEM
    resp_pedido = client.post(
        "/pedidos",
        headers=_headers(token_cliente),
        json={
            "unidadeId": 1,
            "canalPedido": "TOTEM",
            "itens": [
                {"produtoId": 1, "quantidade": 1},
                {"produtoId": 4, "quantidade": 2},
            ],
            "formaPagamento": "MOCK",
        },
    )
    assert resp_pedido.status_code == 201
    pedido = resp_pedido.json()
    pedido_id = pedido["pedidoId"]
    assert pedido["canalPedido"] == "TOTEM"
    assert pedido["status"] == "AGUARDANDO_PAGAMENTO"
    assert pedido["total"] == 45.9

    # 2. Filtrar pedidos por canalPedido=TOTEM
    resp_filtro = client.get("/pedidos?canalPedido=TOTEM", headers=_headers(token_cliente))
    assert resp_filtro.status_code == 200
    assert resp_filtro.json()["total"] == 1

    # 3. Pagamento mock RECUSADO mantem pedido em AGUARDANDO_PAGAMENTO
    resp_recusado = client.post(
        "/pagamentos/mock",
        headers=_headers(token_cliente),
        json={
            "pedidoId": pedido_id,
            "idempotencyKey": "chave-recusada-001",
            "simularResultado": "RECUSADO",
        },
    )
    assert resp_recusado.status_code == 200
    assert resp_recusado.json()["statusPagamento"] == "RECUSADO"
    assert resp_recusado.json()["pedidoStatus"] == "AGUARDANDO_PAGAMENTO"

    # 4. Pagamento mock APROVADO atualiza status para EM_PREPARO e credita pontos
    resp_aprovado = client.post(
        "/pagamentos/mock",
        headers=_headers(token_cliente),
        json={
            "pedidoId": pedido_id,
            "idempotencyKey": "chave-aprovada-001",
            "simularResultado": "APROVADO",
        },
    )
    assert resp_aprovado.status_code == 200
    body_aprov = resp_aprovado.json()
    assert body_aprov["statusPagamento"] == "APROVADO"
    assert body_aprov["pedidoStatus"] == "EM_PREPARO"
    assert body_aprov["idempotenteReaproveitado"] is False

    # 5. Reenvio com a mesma idempotencyKey nao duplica cobranca
    resp_idemp = client.post(
        "/pagamentos/mock",
        headers=_headers(token_cliente),
        json={
            "pedidoId": pedido_id,
            "idempotencyKey": "chave-aprovada-001",
            "simularResultado": "APROVADO",
        },
    )
    assert resp_idemp.status_code == 200
    assert resp_idemp.json()["idempotenteReaproveitado"] is True
    assert resp_idemp.json()["codigoTransacao"] == body_aprov["codigoTransacao"]

    # 6. Cozinha atualiza status EM_PREPARO -> PRONTO -> ENTREGUE
    resp_pronto = client.patch(
        f"/pedidos/{pedido_id}/status",
        headers=_headers(token_cozinha),
        json={"status": "PRONTO"},
    )
    assert resp_pronto.status_code == 200
    assert resp_pronto.json()["status"] == "PRONTO"

    resp_entregue = client.patch(
        f"/pedidos/{pedido_id}/status",
        headers=_headers(token_cozinha),
        json={"status": "ENTREGUE"},
    )
    assert resp_entregue.status_code == 200
    assert resp_entregue.json()["status"] == "ENTREGUE"

    # 7. Conferir pontos de fidelidade creditados (50 iniciais + 4 pontos de R$ 45,90 = 54)
    resp_fid = client.get("/fidelidade/me", headers=_headers(token_cliente))
    assert resp_fid.status_code == 200
    assert resp_fid.json()["saldoPontos"] == 54

    # 8. Conferir relatorio consolidado da Matriz
    resp_rel = client.get("/relatorios/matriz", headers=_headers(token_matriz))
    assert resp_rel.status_code == 200
    assert resp_rel.json()["resumoGeral"]["totalPedidosPagos"] == 1

    # 9. Conferir trilha de auditoria (PEDIDO_CRIADO, PAGAMENTO_APROVADO, PEDIDO_STATUS_ATUALIZADO)
    resp_audit = client.get("/auditoria/logs?acao=PEDIDO_CRIADO", headers=_headers(token_matriz))
    assert resp_audit.status_code == 200
    assert resp_audit.json()["total"] >= 1


# T10 - Cancelamento estorna estoque automaticamente (Positivo)
def test_t10_cancelamento_estorna_estoque(client: TestClient):
    token_cliente = _obter_token(client, "cliente@raizesdonordeste.com.br")

    # Saldo inicial do produto 6 na unidade 1 e 2
    resp_pedido = client.post(
        "/pedidos",
        headers=_headers(token_cliente),
        json={
            "unidadeId": 1,
            "canalPedido": "APP",
            "itens": [{"produtoId": 6, "quantidade": 2}],
            "formaPagamento": "PIX",
        },
    )
    assert resp_pedido.status_code == 201
    pedido_id = resp_pedido.json()["pedidoId"]

    # Cancelar pedido deve devolver as 2 unidades ao estoque
    resp_cancel = client.post(
        f"/pedidos/{pedido_id}/cancelar",
        headers=_headers(token_cliente),
        json={"motivo": "Cliente desistiu antes do pagamento"},
    )
    assert resp_cancel.status_code == 200
    assert resp_cancel.json()["status"] == "CANCELADO"

    # Conferir que o produto 6 voltou a ter 2 unidades disponiveis no cardapio
    cardapio = client.get("/unidades/1/cardapio").json()["items"]
    canjica = [item for item in cardapio if item["produtoId"] == 6][0]
    assert canjica["quantidadeEstoque"] == 2


# T11 - Regra da franquia: unidade de formato reduzido bloqueia item de cozinha completa (Negativo)
def test_t11_formato_reduzido_bloqueia_cozinha_completa(client: TestClient):
    token_cliente = _obter_token(client, "cliente@raizesdonordeste.com.br")
    # Unidade 3 (SPO-01) e FORMATO_REDUZIDO; Produto 1 (Cuscuz) exige COZINHA_COMPLETA
    resp = client.post(
        "/pedidos",
        headers=_headers(token_cliente),
        json={
            "unidadeId": 3,
            "canalPedido": "PICKUP",
            "itens": [{"produtoId": 1, "quantidade": 1}],
            "formaPagamento": "MOCK",
        },
    )
    assert resp.status_code == 409
    assert resp.json()["error"] == "PRODUTO_INDISPONIVEL_NA_UNIDADE"


# T12 - Cadastro e Anonimizacao LGPD (Positivo)
def test_t12_cadastro_e_anonimizacao_lgpd(client: TestClient):
    resp_cad = client.post(
        "/auth/cadastro",
        json={
            "nome": "Severino Teste LGPD",
            "email": "severino.lgpd@exemplo.com",
            "senha": "Senha@123",
            "consentimentoLgpd": True,
            "consentimentoFidelidade": True,
            "faixaEtaria": "35-44",
        },
    )
    assert resp_cad.status_code == 201

    token = _obter_token(client, "severino.lgpd@exemplo.com")
    resp_anon = client.post("/usuarios/me/anonimizar", headers=_headers(token))
    assert resp_anon.status_code == 200
    assert resp_anon.json()["anonimizado"] is True
    assert "anon_" in resp_anon.json()["email"]

    # Token antigo deixa de funcionar apos anonimizacao
    resp_pos = client.get("/usuarios/me", headers=_headers(token))
    assert resp_pos.status_code == 401