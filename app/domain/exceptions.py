from typing import Any


class DomainError(Exception):
    def __init__(
        self,
        error_code: str,
        message: str,
        status_code: int = 400,
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(message)
        self.error_code = error_code
        self.message = message
        self.status_code = status_code
        self.details = details or []


class NaoAutenticadoError(DomainError):
    def __init__(self, message: str = "Autenticacao obrigatoria ou token invalido.") -> None:
        super().__init__("NAO_AUTENTICADO", message, status_code=401)


class SemPermissaoError(DomainError):
    def __init__(self, message: str = "Perfil sem permissao para esta operacao.") -> None:
        super().__init__("SEM_PERMISSAO", message, status_code=403)


class RecursoNaoEncontradoError(DomainError):
    def __init__(self, message: str = "Recurso nao encontrado.", details: list[dict[str, Any]] | None = None) -> None:
        super().__init__("RECURSO_NAO_ENCONTRADO", message, status_code=404, details=details)


class ConflitoNegocioError(DomainError):
    def __init__(
        self,
        error_code: str = "CONFLITO_REGRA_NEGOCIO",
        message: str = "Operacao violou uma regra de negocio.",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__(error_code, message, status_code=409, details=details)


class ValidacaoDominioError(DomainError):
    def __init__(
        self,
        message: str = "Dados invalidos para a operacao.",
        details: list[dict[str, Any]] | None = None,
    ) -> None:
        super().__init__("ERRO_VALIDACAO", message, status_code=422, details=details)