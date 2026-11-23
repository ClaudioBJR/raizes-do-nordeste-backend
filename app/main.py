import uuid
from fastapi import FastAPI, Request
from app.api.error_handlers import registrar_error_handlers
from app.api.routers import auth_router, catalogo_router, gestao_router, pedidos_router
from app.config import get_settings

settings = get_settings()

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description=(
        "API REST de Back-end da Rede Raizes do Nordeste: gestao de unidades heterogeneas, "
        "cardapio sazonal e local, estoque por unidade, pedidos multicanal (canalPedido), "
        "pagamento desacoplado (mock) com idempotencia, fidelizacao progressiva, LGPD e auditoria."
    ),
)


@app.middleware("http")
async def adicionar_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-Id") or str(uuid.uuid4())
    request.state.request_id = request_id
    response = await call_next(request)
    response.headers["X-Request-Id"] = request_id
    return response


registrar_error_handlers(app)


@app.get("/health", tags=["Sistema"], summary="Verificacao de disponibilidade da API")
def healthcheck():
    return {
        "status": "ok",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
    }


app.include_router(auth_router.router)
app.include_router(catalogo_router.router)
app.include_router(pedidos_router.router)
app.include_router(gestao_router.router)