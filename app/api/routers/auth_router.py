from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session
from app.api.dependencies import obter_usuario_atual
from app.api.schemas import CadastroIn, LoginIn, LoginOut, UsuarioOut
from app.application import auth_service
from app.infrastructure.database import get_db
from app.infrastructure.models import UsuarioModel

router = APIRouter(tags=["Auth e Usuarios"])


def _serializar_usuario(u: UsuarioModel) -> UsuarioOut:
    return UsuarioOut(
        id=u.id,
        nome=u.nome,
        email=u.email,
        perfil=u.perfil,
        faixaEtaria=u.faixa_etaria,
        consentimentoLgpd=u.consentimento_lgpd,
        consentimentoFidelidade=u.consentimento_fidelidade,
        anonimizado=u.anonimizado,
        criadoEm=u.criado_em,
    )


@router.post("/auth/cadastro", response_model=UsuarioOut, status_code=status.HTTP_201_CREATED, summary="Cadastrar cliente com consentimento LGPD")
def cadastrar(payload: CadastroIn, db: Session = Depends(get_db)):
    usuario = auth_service.registrar_usuario(
        db=db,
        nome=payload.nome,
        email=payload.email,
        senha=payload.senha,
        consentimento_lgpd=payload.consentimentoLgpd,
        consentimento_fidelidade=payload.consentimentoFidelidade,
        faixa_etaria=payload.faixaEtaria,
    )
    return _serializar_usuario(usuario)


@router.post("/auth/login", response_model=LoginOut, summary="Autenticar usuario e gerar token JWT")
def login(payload: LoginIn, db: Session = Depends(get_db)):
    return auth_service.autenticar_usuario(db=db, email=payload.email, senha=payload.senha)


@router.get("/usuarios/me", response_model=UsuarioOut, summary="Consultar dados do usuario autenticado")
def meu_perfil(usuario: UsuarioModel = Depends(obter_usuario_atual)):
    return _serializar_usuario(usuario)


@router.post("/usuarios/me/anonimizar", response_model=UsuarioOut, summary="Solicitar anonimizacao de dados pessoais (LGPD)")
def anonimizar_meus_dados(
    db: Session = Depends(get_db),
    usuario: UsuarioModel = Depends(obter_usuario_atual),
):
    atualizado = auth_service.anonimizar_usuario(db=db, usuario=usuario)
    return _serializar_usuario(atualizado)