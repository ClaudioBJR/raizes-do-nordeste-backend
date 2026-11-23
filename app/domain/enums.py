from enum import Enum


class PerfilUsuario(str, Enum):
    CLIENTE = "CLIENTE"
    ATENDENTE = "ATENDENTE"
    COZINHA = "COZINHA"
    GERENTE = "GERENTE"
    MATRIZ = "MATRIZ"


class CanalPedido(str, Enum):
    APP = "APP"
    TOTEM = "TOTEM"
    BALCAO = "BALCAO"
    PICKUP = "PICKUP"
    WEB = "WEB"


class StatusPedido(str, Enum):
    AGUARDANDO_PAGAMENTO = "AGUARDANDO_PAGAMENTO"
    EM_PREPARO = "EM_PREPARO"
    PRONTO = "PRONTO"
    ENTREGUE = "ENTREGUE"
    CANCELADO = "CANCELADO"


class FormaPagamento(str, Enum):
    PIX = "PIX"
    CARTAO_CREDITO = "CARTAO_CREDITO"
    CARTAO_DEBITO = "CARTAO_DEBITO"
    MOCK = "MOCK"


class StatusPagamento(str, Enum):
    PENDENTE = "PENDENTE"
    APROVADO = "APROVADO"
    RECUSADO = "RECUSADO"


class TipoOperacaoUnidade(str, Enum):
    COZINHA_COMPLETA = "COZINHA_COMPLETA"
    FORMATO_REDUZIDO = "FORMATO_REDUZIDO"


class RegiaoBrasil(str, Enum):
    NORDESTE = "NORDESTE"
    SUDESTE = "SUDESTE"
    SUL = "SUL"
    CENTRO_OESTE = "CENTRO_OESTE"
    NORTE = "NORTE"


class CategoriaProduto(str, Enum):
    CUSCUZ = "CUSCUZ"
    TAPIOCA = "TAPIOCA"
    BOLOS = "BOLOS"
    BEBIDAS = "BEBIDAS"
    SAZONAL = "SAZONAL"


class TipoMovimentacaoEstoque(str, Enum):
    ENTRADA = "ENTRADA"
    SAIDA = "SAIDA"
    ESTORNO = "ESTORNO"
    AJUSTE = "AJUSTE"


class NivelFidelidade(str, Enum):
    BRONZE = "BRONZE"
    PRATA = "PRATA"
    OURO = "OURO"


class TipoMovimentacaoFidelidade(str, Enum):
    CREDITO = "CREDITO"
    RESGATE = "RESGATE"