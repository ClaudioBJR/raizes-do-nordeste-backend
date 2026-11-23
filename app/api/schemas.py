from datetime import datetime
from decimal import Decimal
from typing import Any
from pydantic import BaseModel, EmailStr, Field
from app.domain.enums import (
    CanalPedido,
    CategoriaProduto,
    FormaPagamento,
    RegiaoBrasil,
    StatusPagamento,
    StatusPedido,
    TipoMovimentacaoEstoque,
    TipoOperacaoUnidade,
)


# --- Erro padronizado ---
class ErrorDetail(BaseModel):
    field: str
    issue: str


class ErrorResponse(BaseModel):
    error: str
    message: str
    details: list[ErrorDetail] = []
    timestamp: str
    path: str
    requestId: str


# --- Auth e Usuarios ---
class CadastroIn(BaseModel):
    nome: str = Field(..., min_length=2, max_length=120, examples=["Joao da Silva"])
    email: EmailStr = Field(..., examples=["joao.cliente@exemplo.com"])
    senha: str = Field(..., min_length=6, max_length=72, examples=["Senha@123"])
    consentimentoLgpd: bool = Field(..., examples=[True])
    consentimentoFidelidade: bool = Field(default=False, examples=[True])
    faixaEtaria: str | None = Field(default=None, max_length=20, examples=["25-34"])


class LoginIn(BaseModel):
    email: EmailStr = Field(..., examples=["cliente@raizesdonordeste.com.br"])
    senha: str = Field(..., min_length=1, examples=["Senha@123"])


class UsuarioOut(BaseModel):
    id: int
    nome: str
    email: str
    perfil: str
    faixaEtaria: str | None = None
    consentimentoLgpd: bool
    consentimentoFidelidade: bool
    anonimizado: bool
    criadoEm: datetime


class LoginUserOut(BaseModel):
    id: int
    nome: str
    email: str
    perfil: str
    consentimentoFidelidade: bool


class LoginOut(BaseModel):
    accessToken: str
    tokenType: str
    expiresIn: int
    user: LoginUserOut


# --- Unidades, Produtos e Estoque ---
class UnidadeIn(BaseModel):
    nome: str = Field(..., min_length=3, max_length=140, examples=["Fortaleza - Beira Mar"])
    codigo: str = Field(..., min_length=2, max_length=20, examples=["FOR-01"])
    cidade: str = Field(..., min_length=2, max_length=100, examples=["Fortaleza"])
    regiao: RegiaoBrasil = Field(..., examples=["NORDESTE"])
    tipoOperacao: TipoOperacaoUnidade = Field(..., examples=["COZINHA_COMPLETA"])
    horarioFuncionamento: str = Field(default="07:00-22:00", max_length=60)


class UnidadeOut(BaseModel):
    id: int
    nome: str
    codigo: str
    cidade: str
    regiao: str
    tipoOperacao: str
    horarioFuncionamento: str
    ativo: bool


class ProdutoIn(BaseModel):
    nome: str = Field(..., min_length=2, max_length=140, examples=["Pamonha Doce Junina"])
    descricao: str = Field(default="", max_length=300)
    categoria: CategoriaProduto = Field(..., examples=["SAZONAL"])
    precoBase: Decimal = Field(..., gt=0, examples=[15.90])
    sazonal: bool = Field(default=False)
    periodoSazonal: str | None = Field(default=None, max_length=40, examples=["JUNINO"])
    requerCozinhaCompleta: bool = Field(default=False)


class ProdutoOut(BaseModel):
    id: int
    nome: str
    descricao: str
    categoria: str
    precoBase: float
    sazonal: bool
    periodoSazonal: str | None = None
    requerCozinhaCompleta: bool
    ativo: bool


class CardapioItemOut(BaseModel):
    produtoId: int
    nome: str
    descricao: str
    categoria: str
    precoBase: float
    sazonal: bool
    periodoSazonal: str | None = None
    requerCozinhaCompleta: bool
    quantidadeEstoque: int
    disponivel: bool


class MovimentacaoEstoqueIn(BaseModel):
    unidadeId: int = Field(..., ge=1, examples=[1])
    produtoId: int = Field(..., ge=1, examples=[1])
    tipo: TipoMovimentacaoEstoque = Field(..., examples=["ENTRADA"])
    quantidade: int = Field(..., ge=1, examples=[10])
    motivo: str = Field(..., min_length=3, max_length=200, examples=["Reposicao matinal"])


class EstoqueOut(BaseModel):
    id: int
    unidadeId: int
    produtoId: int
    quantidade: int
    disponivelUnidade: bool
    atualizadoEm: datetime


# --- Pedidos e Pagamentos ---
class PedidoItemIn(BaseModel):
    produtoId: int = Field(..., ge=1, examples=[1])
    quantidade: int = Field(..., ge=1, examples=[2])


class PedidoCreateIn(BaseModel):
    unidadeId: int = Field(..., ge=1, examples=[1])
    canalPedido: CanalPedido = Field(..., examples=["TOTEM"])
    itens: list[PedidoItemIn] = Field(..., min_length=1)
    formaPagamento: FormaPagamento = Field(default=FormaPagamento.MOCK, examples=["MOCK"])
    usarPontosFidelidade: int = Field(default=0, ge=0, examples=[0])


class PedidoItemOut(BaseModel):
    produtoId: int
    quantidade: int
    precoUnitario: float
    subtotal: float


class PedidoOut(BaseModel):
    pedidoId: int
    clienteId: int
    unidadeId: int
    canalPedido: str
    status: str
    subtotal: float
    descontoFidelidade: float
    total: float
    formaPagamento: str
    itens: list[PedidoItemOut]
    createdAt: datetime


class AtualizarStatusPedidoIn(BaseModel):
    status: StatusPedido = Field(..., examples=["PRONTO"])


class CancelarPedidoIn(BaseModel):
    motivo: str = Field(default="Cancelado a pedido do cliente", min_length=3, max_length=200)


class PagamentoMockIn(BaseModel):
    pedidoId: int = Field(..., ge=1, examples=[1])
    idempotencyKey: str = Field(..., min_length=4, max_length=100, examples=["pagto-pedido-1-tentativa-1"])
    simularResultado: StatusPagamento = Field(default=StatusPagamento.APROVADO, examples=["APROVADO"])


class PagamentoMockOut(BaseModel):
    pagamentoId: int
    pedidoId: int
    idempotencyKey: str
    idempotenteReaproveitado: bool
    provedor: str
    statusPagamento: str
    pedidoStatus: str
    valor: float
    codigoTransacao: str
    mensagem: str
    gatewayPayload: dict[str, Any]
    processadoEm: datetime


# --- Fidelidade e Auditoria ---
class FidelidadeMovOut(BaseModel):
    id: int
    pedidoId: int | None
    tipo: str
    pontos: int
    criadoEm: datetime


class FidelidadeContaOut(BaseModel):
    usuarioId: int
    saldoPontos: int
    totalPedidosPagos: int
    nivel: str
    historico: list[FidelidadeMovOut]


class AuditLogOut(BaseModel):
    id: int
    usuarioId: int | None
    acao: str
    entidade: str
    entidadeId: int | None
    detalhes: dict[str, Any]
    criadoEm: datetime