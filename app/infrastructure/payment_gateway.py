import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from app.domain.enums import StatusPagamento


class MockPaymentGateway:
    """Simulador desacoplado de gateway externo de pagamento."""

    PROVEDOR = "MOCK_GATEWAY_RAIZES"

    def processar_cobranca(
        self,
        pedido_id: int,
        valor: Decimal,
        forma_pagamento: str,
        simular_resultado: StatusPagamento,
    ) -> dict[str, str]:
        codigo_transacao = f"TXN-{uuid.uuid4().hex[:12].upper()}"
        aprovado = simular_resultado == StatusPagamento.APROVADO

        payload = {
            "provider": self.PROVEDOR,
            "transactionId": codigo_transacao,
            "pedidoId": pedido_id,
            "formaPagamento": forma_pagamento,
            "amount": float(valor),
            "currency": "BRL",
            "status": simular_resultado.value,
            "authorizationCode": f"AUTH{uuid.uuid4().hex[:6].upper()}" if aprovado else None,
            "declineReason": None if aprovado else "PAGAMENTO_RECUSADO_PELO_EMISSOR_MOCK",
            "processedAt": datetime.now(timezone.utc).isoformat(),
        }

        return {
            "provedor": self.PROVEDOR,
            "status": simular_resultado.value,
            "codigo_transacao": codigo_transacao,
            "payload_retorno": json.dumps(payload, ensure_ascii=False),
        }