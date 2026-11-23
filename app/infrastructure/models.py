from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship
from app.infrastructure.database import Base


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class UsuarioModel(Base):
    __tablename__ = "usuarios"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(120), nullable=False)
    email = Column(String(180), unique=True, nullable=False, index=True)
    senha_hash = Column(String(255), nullable=False)
    perfil = Column(String(30), nullable=False, default="CLIENTE")
    faixa_etaria = Column(String(20), nullable=True)
    consentimento_lgpd = Column(Boolean, nullable=False, default=True)
    consentimento_fidelidade = Column(Boolean, nullable=False, default=False)
    consentimento_em = Column(DateTime(timezone=True), nullable=True)
    anonimizado = Column(Boolean, nullable=False, default=False)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    pedidos = relationship("PedidoModel", back_populates="cliente")
    conta_fidelidade = relationship("FidelidadeContaModel", back_populates="usuario", uselist=False)


class UnidadeModel(Base):
    __tablename__ = "unidades"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(140), nullable=False)
    codigo = Column(String(20), unique=True, nullable=False, index=True)
    cidade = Column(String(100), nullable=False)
    regiao = Column(String(30), nullable=False)
    tipo_operacao = Column(String(30), nullable=False)
    horario_funcionamento = Column(String(60), nullable=False, default="07:00-22:00")
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    estoques = relationship("EstoqueUnidadeModel", back_populates="unidade")
    pedidos = relationship("PedidoModel", back_populates="unidade")


class ProdutoModel(Base):
    __tablename__ = "produtos"

    id = Column(Integer, primary_key=True, index=True)
    nome = Column(String(140), nullable=False)
    descricao = Column(String(300), nullable=False, default="")
    categoria = Column(String(30), nullable=False)
    preco_base = Column(Numeric(10, 2), nullable=False)
    sazonal = Column(Boolean, nullable=False, default=False)
    periodo_sazonal = Column(String(40), nullable=True)
    requer_cozinha_completa = Column(Boolean, nullable=False, default=False)
    ativo = Column(Boolean, nullable=False, default=True)
    criado_em = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    estoques = relationship("EstoqueUnidadeModel", back_populates="produto")


class EstoqueUnidadeModel(Base):
    __tablename__ = "estoque_unidade"
    __table_args__ = (
        UniqueConstraint("unidade_id", "produto_id", name="uq_estoque_unidade_produto"),
    )

    id = Column(Integer, primary_key=True, index=True)
    unidade_id = Column(Integer, ForeignKey("unidades.id"), nullable=False, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False, index=True)
    quantidade = Column(Integer, nullable=False, default=0)
    disponivel_unidade = Column(Boolean, nullable=False, default=True)
    atualizado_em = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    unidade = relationship("UnidadeModel", back_populates="estoques")
    produto = relationship("ProdutoModel", back_populates="estoques")
    movimentacoes = relationship("MovimentacaoEstoqueModel", back_populates="estoque")


class MovimentacaoEstoqueModel(Base):
    __tablename__ = "movimentacoes_estoque"

    id = Column(Integer, primary_key=True, index=True)
    estoque_id = Column(Integer, ForeignKey("estoque_unidade.id"), nullable=False, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=True, index=True)
    tipo = Column(String(20), nullable=False)
    quantidade = Column(Integer, nullable=False)
    motivo = Column(String(200), nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    estoque = relationship("EstoqueUnidadeModel", back_populates="movimentacoes")


class PedidoModel(Base):
    __tablename__ = "pedidos"
    __table_args__ = (
        Index("ix_pedidos_canal_status", "canal_pedido", "status"),
        Index("ix_pedidos_unidade_criado", "unidade_id", "criado_em"),
    )

    id = Column(Integer, primary_key=True, index=True)
    cliente_id = Column(Integer, ForeignKey("usuarios.id"), nullable=False, index=True)
    unidade_id = Column(Integer, ForeignKey("unidades.id"), nullable=False, index=True)
    canal_pedido = Column(String(20), nullable=False, index=True)
    status = Column(String(30), nullable=False, default="AGUARDANDO_PAGAMENTO", index=True)
    subtotal = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    desconto_fidelidade = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    valor_total = Column(Numeric(10, 2), nullable=False, default=Decimal("0.00"))
    forma_pagamento = Column(String(30), nullable=False, default="MOCK")
    criado_em = Column(DateTime(timezone=True), nullable=False, default=utcnow)
    atualizado_em = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    cliente = relationship("UsuarioModel", back_populates="pedidos")
    unidade = relationship("UnidadeModel", back_populates="pedidos")
    itens = relationship("PedidoItemModel", back_populates="pedido", cascade="all, delete-orphan")
    pagamentos = relationship("PagamentoModel", back_populates="pedido")


class PedidoItemModel(Base):
    __tablename__ = "pedido_itens"

    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False, index=True)
    produto_id = Column(Integer, ForeignKey("produtos.id"), nullable=False, index=True)
    quantidade = Column(Integer, nullable=False)
    preco_unitario = Column(Numeric(10, 2), nullable=False)
    subtotal = Column(Numeric(10, 2), nullable=False)

    pedido = relationship("PedidoModel", back_populates="itens")
    produto = relationship("ProdutoModel")


class PagamentoModel(Base):
    __tablename__ = "pagamentos"

    id = Column(Integer, primary_key=True, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=False, index=True)
    idempotency_key = Column(String(100), unique=True, nullable=False, index=True)
    provedor = Column(String(50), nullable=False, default="MOCK_GATEWAY")
    status = Column(String(20), nullable=False)
    valor = Column(Numeric(10, 2), nullable=False)
    codigo_transacao = Column(String(100), nullable=False)
    payload_retorno = Column(Text, nullable=False)
    processado_em = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    pedido = relationship("PedidoModel", back_populates="pagamentos")


class FidelidadeContaModel(Base):
    __tablename__ = "fidelidade_contas"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), unique=True, nullable=False, index=True)
    saldo_pontos = Column(Integer, nullable=False, default=0)
    total_pedidos_pagos = Column(Integer, nullable=False, default=0)
    nivel = Column(String(20), nullable=False, default="BRONZE")
    atualizado_em = Column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    usuario = relationship("UsuarioModel", back_populates="conta_fidelidade")
    movimentacoes = relationship("FidelidadeMovimentacaoModel", back_populates="conta")


class FidelidadeMovimentacaoModel(Base):
    __tablename__ = "fidelidade_movimentacoes"

    id = Column(Integer, primary_key=True, index=True)
    conta_id = Column(Integer, ForeignKey("fidelidade_contas.id"), nullable=False, index=True)
    pedido_id = Column(Integer, ForeignKey("pedidos.id"), nullable=True, index=True)
    tipo = Column(String(20), nullable=False)
    pontos = Column(Integer, nullable=False)
    criado_em = Column(DateTime(timezone=True), nullable=False, default=utcnow)

    conta = relationship("FidelidadeContaModel", back_populates="movimentacoes")


class AuditLogModel(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    usuario_id = Column(Integer, ForeignKey("usuarios.id"), nullable=True, index=True)
    acao = Column(String(80), nullable=False, index=True)
    entidade = Column(String(60), nullable=False)
    entidade_id = Column(Integer, nullable=True)
    detalhes = Column(Text, nullable=False, default="{}")
    criado_em = Column(DateTime(timezone=True), nullable=False, default=utcnow, index=True)