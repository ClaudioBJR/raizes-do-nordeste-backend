from datetime import datetime, timezone
from sqlalchemy.orm import Session
from app.application.audit_service import registrar_auditoria
from app.domain.enums import PerfilUsuario
from app.domain.exceptions import (
    ConflitoNegocioError,
    DomainError,
    ValidacaoDominioError,
)
from app.infrastructure.models import FidelidadeContaModel, UsuarioModel
from app.infrastructure.security import (
    criar_token_jwt,
    gerar_hash_senha,
    verificar_senha,
)


def registrar_usuario(
    db: Session,
    nome: str,
    email: str,
    senha: str,
    consentimento_lgpd: bool,
    consentimento_fidelidade: bool = False,
    faixa_etaria: str | None = None,
) -> UsuarioModel:
    if not consentimento_lgpd:
        raise ValidacaoDominioError(
            message="O consentimento LGPD e obrigatorio para realizar o cadastro.",
            details=[{"field": "consentimentoLgpd", "issue": "Deve ser true"}],
        )

    email_normalizado = email.strip().lower()
    existente = db.query(UsuarioModel).filter(UsuarioModel.email == email_normalizado).first()
    if existente:
        raise ConflitoNegocioError(
            error_code="EMAIL_JA_CADASTRADO",
            message="Ja existe um usuario cadastrado com este e-mail.",
            details=[{"field": "email", "issue": "E-mail ja utilizado"}],
        )

    agora = datetime.now(timezone.utc)
    usuario = UsuarioModel(
        nome=nome.strip(),
        email=email_normalizado,
        senha_hash=gerar_hash_senha(senha),
        perfil=PerfilUsuario.CLIENTE.value,
        faixa_etaria=faixa_etaria if consentimento_fidelidade else None,
        consentimento_lgpd=True,
        consentimento_fidelidade=consentimento_fidelidade,
        consentimento_em=agora,
        anonimizado=False,
        ativo=True,
    )
    db.add(usuario)
    db.flush()

    if consentimento_fidelidade:
        db.add(
            FidelidadeContaModel(
                usuario_id=usuario.id,
                saldo_pontos=0,
                total_pedidos_pagos=0,
                nivel="BRONZE",
            )
        )

    registrar_auditoria(
        db=db,
        acao="USUARIO_CADASTRADO",
        entidade="USUARIOS",
        entidade_id=usuario.id,
        usuario_id=usuario.id,
        detalhes={"consentimentoFidelidade": consentimento_fidelidade},
    )
    db.commit()
    db.refresh(usuario)
    return usuario


def autenticar_usuario(db: Session, email: str, senha: str) -> dict:
    email_normalizado = email.strip().lower()
    usuario = db.query(UsuarioModel).filter(UsuarioModel.email == email_normalizado).first()

    if (
        not usuario
        or not usuario.ativo
        or usuario.anonimizado
        or not verificar_senha(senha, usuario.senha_hash)
    ):
        raise DomainError(
            error_code="CREDENCIAIS_INVALIDAS",
            message="E-mail ou senha invalidos.",
            status_code=401,
        )

    token, expires_in = criar_token_jwt(
        user_id=usuario.id,
        email=usuario.email,
        perfil=usuario.perfil,
    )

    registrar_auditoria(
        db=db,
        acao="LOGIN_REALIZADO",
        entidade="USUARIOS",
        entidade_id=usuario.id,
        usuario_id=usuario.id,
        detalhes={"perfil": usuario.perfil},
    )
    db.commit()

    return {
        "accessToken": token,
        "tokenType": "Bearer",
        "expiresIn": expires_in,
        "user": {
            "id": usuario.id,
            "nome": usuario.nome,
            "email": usuario.email,
            "perfil": usuario.perfil,
            "consentimentoFidelidade": usuario.consentimento_fidelidade,
        },
    }


def anonimizar_usuario(db: Session, usuario: UsuarioModel) -> UsuarioModel:
    if usuario.anonimizado:
        raise ConflitoNegocioError(
            error_code="USUARIO_JA_ANONIMIZADO",
            message="Os dados deste usuario ja foram anonimizados.",
        )

    usuario.nome = f"Usuario Anonimizado #{usuario.id}"
    usuario.email = f"anon_{usuario.id}@anonimizado.local"
    usuario.faixa_etaria = None
    usuario.consentimento_fidelidade = False
    usuario.anonimizado = True
    usuario.ativo = False

    registrar_auditoria(
        db=db,
        acao="USUARIO_ANONIMIZADO_LGPD",
        entidade="USUARIOS",
        entidade_id=usuario.id,
        usuario_id=usuario.id,
        detalhes={"motivo": "Solicitacao do titular conforme LGPD"},
    )
    db.commit()
    db.refresh(usuario)
    return usuario