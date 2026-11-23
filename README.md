# API Back-end — Rede Raízes do Nordeste

API REST desenvolvida em **Python + FastAPI + SQLAlchemy + Alembic + SQLite** para a disciplina de Projeto Multidisciplinar (Trilha Back-end), atendendo ao estudo de caso da **Rede Raízes do Nordeste**.

## Funcionalidades Entregues (MVP)
- **Autenticação e Autorização (RBAC):** JWT com expiração, hash de senha com `bcrypt` e perfis `CLIENTE`, `ATENDENTE`, `COZINHA`, `GERENTE` e `MATRIZ`.
- **Unidades Heterogêneas e Cardápio Sazonal:** suporte a unidades `COZINHA_COMPLETA` e `FORMATO_REDUZIDO`, itens sazonais (período junino) e bloqueio de venda de pratos incompatíveis com a estrutura da loja.
- **Estoque Local por Unidade:** controle de saldo segregado por `(unidade_id, produto_id)`, reserva atômica na criação do pedido, bloqueio por saldo insuficiente (`409`) e estorno automático no cancelamento.
- **Multicanalidade (`canalPedido`):** exigência de `APP`, `TOTEM`, `BALCAO`, `PICKUP` ou `WEB` na criação de pedidos e consulta filtrável (`GET /pedidos?canalPedido=TOTEM`).
- **Pagamento Desacoplado (Mock) com Idempotência:** simulação de gateway externo (`APROVADO` / `RECUSADO`) com chave única `idempotencyKey`.
- **Programa de Fidelização e LGPD:** consentimento explícito no cadastro, acúmulo de pontos/níveis progressivos (`BRONZE`, `PRATA`, `OURO`) e endpoint de anonimização de dados pessoais (`POST /usuarios/me/anonimizar`).
- **Relatórios da Matriz e Auditoria:** consolidado de vendas por unidade, região, canal e produtos mais consumidos, além da trilha `audit_logs` para ações sensíveis.

## Arquitetura em 4 Camadas
```text
app/
├── domain/          # Enums, exceções de negócio e regras puras de domínio
├── application/     # Serviços / Casos de uso (pedidos, estoque, pagamento mock, LGPD, relatórios)
├── infrastructure/  # SQLAlchemy ORM, banco SQLite, JWT/bcrypt, gateway mock e seed
├── api/             # Routers FastAPI, schemas Pydantic, RBAC e error handlers padronizados
└── main.py          # Entrada da aplicação, middleware X-Request-Id e OpenAPI/Swagger
alembic/             # Migrations versionadas do banco de dados
docs/                # Coleção Postman (.json)
tests/               # Suíte de testes automatizados (pytest)
```

## Requisitos do Ambiente
- Python **3.10+**
- Git

## Como Executar Localmente (Passo a Passo)

1. **Clonar o repositório e acessar a pasta:**
```bash
git clone [https://github.com/ClaudioBJR/raizes-do-nordeste-backend.git](https://github.com/ClaudioBJR/raizes-do-nordeste-backend.git)
cd raizes-do-nordeste-backend
```

2. **Criar e ativar o ambiente virtual:**
- Windows (PowerShell):
```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
```
- Linux/macOS:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

3. **Instalar as dependências:**
```bash
pip install -r requirements.txt
```

4. **Configurar variáveis de ambiente:**
Copie `.env.example` para `.env` e ajuste `JWT_SECRET_KEY` (mínimo 32 caracteres).
```powershell
Copy-Item .env.example .env
```

5. **Executar as migrations e popular o banco de dados (seed):**
```bash
alembic upgrade head
python -m app.infrastructure.seed
```

6. **Iniciar a API:**
```bash
uvicorn app.main:app --reload
```

## Documentação Interativa (Swagger / OpenAPI)
- **URL local do Swagger:** `http://127.0.0.1:8000/docs`
- **Especificação OpenAPI JSON:** `http://127.0.0.1:8000/openapi.json`

## Credenciais de Teste (Seed)
Todos os usuários criados pelo seed utilizam a senha **`Senha@123`**:

| Perfil | E-mail |
| :--- | :--- |
| `CLIENTE` | `cliente@raizesdonordeste.com.br` |
| `ATENDENTE` | `atendente@raizesdonordeste.com.br` |
| `COZINHA` | `cozinha@raizesdonordeste.com.br` |
| `GERENTE` | `gerente@raizesdonordeste.com.br` |