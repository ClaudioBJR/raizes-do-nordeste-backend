from datetime import datetime, timezone
from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException
from app.domain.exceptions import DomainError


def _agora_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "sem-request-id")


def _montar_erro(
    request: Request,
    status_code: int,
    error: str,
    message: str,
    details: list[dict] | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": error,
            "message": message,
            "details": details or [],
            "timestamp": _agora_iso(),
            "path": request.url.path,
            "requestId": _request_id(request),
        },
    )


def registrar_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(DomainError)
    async def domain_error_handler(request: Request, exc: DomainError) -> JSONResponse:
        return _montar_erro(
            request=request,
            status_code=exc.status_code,
            error=exc.error_code,
            message=exc.message,
            details=exc.details,
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
        detalhes = []
        for err in exc.errors():
            loc = [str(parte) for parte in err.get("loc", []) if parte != "body"]
            campo = ".".join(loc) if loc else "payload"
            detalhes.append({"field": campo, "issue": err.get("msg", "Valor invalido")})

        return _montar_erro(
            request=request,
            status_code=422,
            error="ERRO_VALIDACAO",
            message="Um ou mais campos enviados sao invalidos ou obrigatorios.",
            details=detalhes,
        )

    @app.exception_handler(StarletteHTTPException)
    async def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
        return _montar_erro(
            request=request,
            status_code=exc.status_code,
            error=f"HTTP_{exc.status_code}",
            message=str(exc.detail),
        )

    @app.exception_handler(Exception)
    async def generic_error_handler(request: Request, _exc: Exception) -> JSONResponse:
        return _montar_erro(
            request=request,
            status_code=500,
            error="ERRO_INTERNO",
            message="Ocorreu um erro interno inesperado no servidor.",
        )