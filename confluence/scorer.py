"""
Motor de confluencia: combina señales de varias estrategias en un score
unificado por símbolo. Premia cuando varias estrategias coinciden en
dirección, penaliza cuando solo una tiene señal, y descarta cuando
las estrategias se contradicen entre sí.

Ahora incluye pesos dinámicos basados en el régimen de mercado.
"""
from dataclasses import dataclass
from typing import Optional

# Pesos base por defecto
DEFAULT_WEIGHTS = {
    "trend_following": 0.6,
    "momentum": 0.4,
}

# Pesos adaptativos según el régimen detectado
REGIME_WEIGHTS = {
    "TRENDING": {
        "trend_following": 0.8,
        "momentum": 0.2,
    },
    "RANGING": {
        "trend_following": 0.2,
        "momentum": 0.8,
    },
    "RANDOM": {
        "trend_following": 0.5,
        "momentum": 0.5,
    }
}

# Penalización cuando solo una estrategia tiene señal (la otra está neutral)
PARTIAL_SIGNAL_PENALTY = 0.6  # multiplica el score cuando falta confirmación

@dataclass
class ConfluenceResult:
    symbol: str
    direction: str
    confluence_score: float
    agreement: str  # "full", "partial", "conflict", "none"
    strategy_signals: dict
    regime: Optional[str] = None

def combine_signals(symbol: str, strategy_signals: dict, regime: Optional[str] = None) -> ConfluenceResult:
    """
    Args:
        symbol: nombre del símbolo
        strategy_signals: dict {strategy_name: {"direction": str, "strength": float}}
        regime: régimen de mercado ("TRENDING", "RANGING", "RANDOM")

    Returns:
        ConfluenceResult con dirección final, score, y tipo de acuerdo
    """
    # 1. Determinar qué pesos usar según el régimen
    weights = REGIME_WEIGHTS.get(regime, DEFAULT_WEIGHTS)

    active = {
        name: sig for name, sig in strategy_signals.items()
        if sig["direction"] in ("alcista", "bajista")
    }

    if not active:
        return ConfluenceResult(symbol, "sin_senal", 0.0, "none", strategy_signals, regime)

    directions = set(sig["direction"] for sig in active.values())

    if len(directions) > 1:
        # Las estrategias activas se contradicen entre sí
        return ConfluenceResult(symbol, "sin_senal", 0.0, "conflict", strategy_signals, regime)

    direction = directions.pop()

    # 2. Cálculo de score ponderado con pesos dinámicos
    weighted_sum = sum(
        weights.get(name, 0) * sig["strength"]
        for name, sig in active.items()
    )
    total_weight = sum(weights.get(name, 0) for name in active)
    base_score = weighted_sum / total_weight if total_weight > 0 else 0.0

    total_strategies = len(DEFAULT_WEIGHTS)
    active_strategies = len(active)

    if active_strategies == total_strategies:
        agreement = "full"
        score = base_score
    else:
        agreement = "partial"
        score = base_score * PARTIAL_SIGNAL_PENALTY

    # Penalización extra si el régimen es RANDOM (aumentamos el rigor)
    if regime == "RANDOM":
        score *= 0.7

    return ConfluenceResult(symbol, direction, round(score, 3), agreement, strategy_signals, regime)

if __name__ == "__main__":
    # Ejemplo 1: Tendencia clara en mercado Trending
    ejemplo1 = combine_signals("EURUSD", {
        "trend_following": {"direction": "bajista", "strength": 0.8},
        "momentum": {"direction": "bajista", "strength": 0.5},
    }, regime="TRENDING")
    print(f"Trending: {ejemplo1}")

    # Ejemplo 2: Momentum fuerte en mercado Ranging
    ejemplo2 = combine_signals("USDJPY", {
        "trend_following": {"direction": "sin_senal", "strength": 0.0},
        "momentum": {"direction": "alcista", "strength": 0.9},
    }, regime="RANGING")
    print(f"Ranging: {ejemplo2}")
