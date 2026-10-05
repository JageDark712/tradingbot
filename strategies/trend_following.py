"""
Estrategia de trend following multi-timeframe (D1 sesgo, H4 confirmación, H1 entrada).
Solo genera señal cuando los tres timeframes están alineados en la misma dirección.
"""
from strategies.base_strategy import BaseStrategy
from indicators.trend import get_trend_signal
from config.settings import TIMEFRAMES


class TrendFollowingStrategy(BaseStrategy):
    name = "trend_following"

    def __init__(self, data_fetcher):
        """
        Args:
            data_fetcher: función que recibe (symbol, timeframe, n_candles) y
                          devuelve un DataFrame de velas. Permite usar la misma
                          estrategia con fetch_mt5_candles o fetch_binance_candles.
        """
        self.data_fetcher = data_fetcher

    def evaluate(self, symbol: str) -> dict:
        signals = {}

        for role, timeframe in TIMEFRAMES.items():
            df = self.data_fetcher(symbol, timeframe)
            signals[role] = get_trend_signal(df)

        bias_dir = signals["bias"]["direction"]
        confirm_dir = signals["confirm"]["direction"]
        entry_dir = signals["entry"]["direction"]

        # Señal solo si los tres timeframes coinciden en dirección (y no es "sin_tendencia")
        if bias_dir == confirm_dir == entry_dir and bias_dir != "sin_tendencia":
            direction = bias_dir
            # Fuerza combinada: promedio ponderado (bias pesa más, entry pesa menos)
            strength = (
                signals["bias"]["strength"] * 0.5
                + signals["confirm"]["strength"] * 0.3
                + signals["entry"]["strength"] * 0.2
            )
        else:
            direction = "sin_senal"
            strength = 0.0

        return {
            "direction": direction,
            "strength": round(strength, 3),
            "details": signals,
        }


if __name__ == "__main__":
    from data.fetch_mt5 import fetch_mt5_candles

    strategy = TrendFollowingStrategy(data_fetcher=fetch_mt5_candles)
    result = strategy.evaluate("EURUSD")

    print(f"Dirección: {result['direction']}")
    print(f"Fuerza: {result['strength']}")
    print("\nDetalle por timeframe:")
    for role, signal in result["details"].items():
        print(f"  {role}: {signal['direction']} (strength={signal['strength']}, adx={signal['adx']})")
