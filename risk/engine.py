"""
Motor de gestión de riesgo: calcula tamaño de posición y riesgo monetario
por trade, de forma adaptativa según categoría de activo y fuerza de señal.
También controla límites agregados (riesgo total abierto, trades por
categoría) para evitar sobre-exposición cuando salen varias señales a la vez.
"""
from dataclasses import dataclass, field

from config.settings import (
    RISK_BASE_BY_CATEGORY,
    MAX_AGGREGATE_RISK,
    MAX_TRADES_PER_CATEGORY,
)


@dataclass
class OpenPosition:
    symbol: str
    category: str
    direction: str
    risk_amount: float  # en unidades monetarias (ej. USD)
    risk_pct: float      # % del capital en el momento de abrir


@dataclass
class RiskEngine:
    account_balance: float
    open_positions: list = field(default_factory=list)

    def calculate_trade_risk_pct(self, category: str, signal_strength: float) -> float:
        """
        Calcula el % de riesgo a asumir en un trade, según categoría de
        activo y fuerza de la señal de confluencia.

        riesgo_final = riesgo_base_categoria * (0.5 + 0.5 * strength)
        """
        base_risk = RISK_BASE_BY_CATEGORY.get(category)
        if base_risk is None:
            raise ValueError(f"Categoría desconocida: {category}")

        multiplier = 0.5 + 0.5 * signal_strength
        return base_risk * multiplier

    def current_aggregate_risk_pct(self) -> float:
        """Suma el % de riesgo de todas las posiciones abiertas."""
        return sum(p.risk_pct for p in self.open_positions)

    def count_open_by_category(self, category: str) -> int:
        return sum(1 for p in self.open_positions if p.category == category)

    def can_open_trade(self, category: str, proposed_risk_pct: float) -> tuple[bool, str]:
        """
        Verifica si un nuevo trade puede abrirse sin violar los límites:
        - máximo de trades simultáneos por categoría
        - máximo de riesgo agregado abierto

        Returns:
            (puede_abrir: bool, razón: str)
        """
        if self.count_open_by_category(category) >= MAX_TRADES_PER_CATEGORY:
            return False, f"Límite de {MAX_TRADES_PER_CATEGORY} trades simultáneos en '{category}' alcanzado"

        projected_risk = self.current_aggregate_risk_pct() + proposed_risk_pct
        if projected_risk > MAX_AGGREGATE_RISK:
            return False, (
                f"Riesgo agregado proyectado ({projected_risk:.2%}) "
                f"superaría el máximo permitido ({MAX_AGGREGATE_RISK:.2%})"
            )

        return True, "OK"

    def evaluate_trade(self, symbol: str, category: str, direction: str, signal_strength: float) -> dict:
        """
        Evalúa un trade candidato: calcula su riesgo propuesto y verifica
        si puede abrirse dado el estado actual del motor.

        Returns:
            dict con: can_open, risk_pct, risk_amount, reason
        """
        risk_pct = self.calculate_trade_risk_pct(category, signal_strength)
        can_open, reason = self.can_open_trade(category, risk_pct)
        risk_amount = self.account_balance * risk_pct

        return {
            "symbol": symbol,
            "category": category,
            "direction": direction,
            "signal_strength": signal_strength,
            "risk_pct": round(risk_pct, 5),
            "risk_amount": round(risk_amount, 2),
            "can_open": can_open,
            "reason": reason,
        }

    def calculate_position_size(self, entry_price: float, stop_loss_price: float, risk_amount: float) -> float:
        """
        Calcula el tamaño de posición (en unidades del activo) dado el
        riesgo monetario y la distancia al stop loss.

        tamaño = riesgo_monetario / distancia_al_stop
        """
        distance = abs(entry_price - stop_loss_price)
        if distance == 0:
            raise ValueError("La distancia al stop loss no puede ser cero")
        return risk_amount / distance

    def open_trade(self, symbol: str, category: str, direction: str, risk_pct: float):
        """Registra una posición como abierta, para que cuente en los límites agregados."""
        risk_amount = self.account_balance * risk_pct
        self.open_positions.append(
            OpenPosition(symbol=symbol, category=category, direction=direction,
                         risk_amount=risk_amount, risk_pct=risk_pct)
        )

    def close_trade(self, symbol: str):
        """Quita una posición de la lista de abiertas (al cerrarse el trade)."""
        self.open_positions = [p for p in self.open_positions if p.symbol != symbol]


if __name__ == "__main__":
    engine = RiskEngine(account_balance=500.0)

    # Simula evaluar las señales de tu primer scan real
    candidatos = [
        ("BTCUSDT", "crypto", "alcista", 1.000),
        ("BNBUSDT", "crypto", "alcista", 0.806),
        ("EURUSD", "forex", "bajista", 0.627),
    ]

    for symbol, category, direction, strength in candidatos:
        result = engine.evaluate_trade(symbol, category, direction, strength)
        print(result)

        if result["can_open"]:
            engine.open_trade(symbol, category, direction, result["risk_pct"])

    print(f"\nRiesgo agregado total abierto: {engine.current_aggregate_risk_pct():.2%}")
