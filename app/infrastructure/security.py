from datetime import datetime, timedelta, timezone
from typing import Any
import bcrypt
import jwt
from app.config import get_settings
from app.domain.exceptions import NaoAutenticadoError

settings = get_settings()


def gerar_hash_senha(senha_plana: str) -> str:
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(senha_plana.encode("utf-8"), salt).decode("utf-8")


def verificar_senha(senha_plana: str, senha_hash: str) -> bool:
    return bcrypt.checkpw(senha_plana.encode("utf-8"), senha_hash.encode("utf-8"))


def criar_token_jwt(user_id: int, email: str, perfil: str) -> tuple[str, int]:
    agora = datetime.now(timezone.utc)
    expira_em = agora + timedelta(seconds=settings.JWT_EXPIRES_IN_SECONDS)
    payload: dict[str, Any] = {
        "sub": str(user_id),
        "email": email,
        "perfil": perfil,
        "iat": int(agora.timestamp()),
        "exp": int(expira_em.timestamp()),
    }
    token = jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)
    return token, settings.JWT_EXPIRES_IN_SECONDS


def decodificar_token_jwt(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
    except jwt.ExpiredSignatureError as exc:
        raise NaoAutenticadoError("Token expirado. Faca login novamente.") from exc
    except jwt.InvalidTokenError as exc:
        raise NaoAutenticadoError("Token invalido.") from exc