from collections.abc import Callable
from fastapi import Depends
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session
from app.domain.enums import PerfilUsuario
from app.domain.exceptions import NaoAutenticadoError, SemPermissaoError
from app.infrastructure.database import get_db
from app.infrastructure.models import UsuarioModel
from app.infrastructure.security import decodificar_token_jwt

bearer_scheme = HTTPBearer(auto_error=False)


def obter_usuario_atual(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> UsuarioModel:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise NaoAutenticadoError("Header Authorization com Bearer token e obrigatorio.")

    payload = decodificar_token_jwt(credentials.credentials)
    sub = payload.get("sub")
    if not sub:
        raise NaoAutenticadoError("Token sem identificador de usuario.")

    usuario = db.query(UsuarioModel).filter(UsuarioModel.id == int(sub)).first()
    if not usuario or not usuario.ativo or usuario.anonimizado:
        raise NaoAutenticadoError("Usuario inativo, anonimizado ou inexistente.")

    return usuario


def exigir_perfis(*perfis_permitidos: PerfilUsuario) -> Callable:
    valores = {p.value for p in perfis_permitidos}

    def _verificar(usuario: UsuarioModel = Depends(obter_usuario_atual)) -> UsuarioModel:
        if usuario.perfil not in valores:
            raise SemPermissaoError(
                f"Perfil {usuario.perfil} nao possui permissao. Perfis aceitos: {sorted(valores)}."
            )
        return usuario

    return _verificar