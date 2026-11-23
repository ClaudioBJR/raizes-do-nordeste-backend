from decimal import Decimal, ROUND_HALF_UP
from app.domain.enums import NivelFidelidade, StatusPedido
from app.domain.exceptions import ConflitoNegocioError

TRANSICOES_STATUS_VALIDAS: dict[StatusPedido, set[StatusPedido]] = {
    StatusPedido.AGUARDANDO_PAGAMENTO: {StatusPedido.EM_PREPARO, StatusPedido.CANCELADO},
    StatusPedido.EM_PREPARO: {StatusPedido.PRONTO, StatusPedido.CANCELADO},
    StatusPedido.PRONTO: {StatusPedido.ENTREGUE},
    StatusPedido.ENTREGUE: set(),
    StatusPedido.CANCELADO: set(),
}


def validar_transicao_status(status_atual: StatusPedido, novo_status: StatusPedido) -> None:
    permitidos = TRANSICOES_STATUS_VALIDAS.get(status_atual, set())
    if novo_status not in permitidos:
        raise ConflitoNegocioError(
            error_code="TRANSICAO_STATUS_INVALIDA",
            message=f"Nao e possivel alterar o pedido de {status_atual.value} para {novo_status.value}.",
            details=[{"field": "status", "issue": f"Permitidos: {[s.value for s in permitidos]}"}],
        )


def calcular_pontos_fidelidade(valor_total: Decimal) -> int:
    # 1 ponto a cada R$ 10,00 pagos
    return int(valor_total // Decimal("10"))


def determinar_nivel_fidelidade(total_pedidos_pagos: int) -> NivelFidelidade:
    if total_pedidos_pagos >= 10:
        return NivelFidelidade.OURO
    if total_pedidos_pagos >= 5:
        return NivelFidelidade.PRATA
    return NivelFidelidade.BRONZE


def percentual_desconto_nivel(nivel: NivelFidelidade) -> Decimal:
    tabela = {
        NivelFidelidade.BRONZE: Decimal("0.00"),
        NivelFidelidade.PRATA: Decimal("0.05"),
        NivelFidelidade.OURO: Decimal("0.10"),
    }
    return tabela[nivel]


def calcular_desconto_resgate_pontos(pontos: int) -> Decimal:
    # Cada 10 pontos equivalem a R$ 1,00 de desconto
    valor = Decimal(pontos) / Decimal("10")
    return valor.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)