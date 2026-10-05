"""
Estrategia de momentum cross-sectional: calcula el momentum de cada
símbolo y lo normaliza respecto al resto del universo (ranking relativo),
en vez de evaluar cada activo de forma aislada.
"""
from strategies.base_strategy import BaseStrategy
from indicators.momentum import get_momentum_signal
from config.settings import TIMEFRAMES


class MomentumStrategy(BaseStrategy):
    name = "momentum"

    def __init__(self, data_fetcher):
        self.data_fetcher = data_fetcher

    def evaluate(self, symbol: str) -> dict:
        """
        Evalúa momentum para un solo símbolo (sin ranking cross-sectional
        todavía). Usa el timeframe 'bias' (D1) como base, igual que trend
        following, para que ambas estrategias comparen señales del mismo
        horizonte temporal.
        """
        df = self.data_fetcher(symbol, TIMEFRAMES["bias"])
        signal = get_momentum_signal(df)

        return {
            "direction": signal["direction"],
            "raw_momentum": signal["raw_momentum"],
            "details": signal,
        }

    def evaluate_universe(self, symbols: list) -> dict:
        """
        Evalúa todo el universo y normaliza la fuerza de cada señal
        respecto al momentum máximo absoluto encontrado (ranking relativo).

        Returns:
            dict {symbol: {direction, strength, raw_momentum}}
        """
        raw_results = {}
        for symbol in symbols:
            try:
                raw_results[symbol] = self.evaluate(symbol)
            except Exception as e:
                print(f"  [ERROR momentum] {symbol}: {e}")

        valid = {s: r for s, r in raw_results.items() if r["raw_momentum"] is not None}
        if not valid:
            return {}

        max_abs_momentum = max(abs(r["raw_momentum"]) for r in valid.values())

        results = {}
        for symbol, r in valid.items():
            strength = abs(r["raw_momentum"]) / max_abs_momentum if max_abs_momentum > 0 else 0.0
            results[symbol] = {
                "direction": r["direction"],
                "strength": round(strength, 3),
                "raw_momentum": r["raw_momentum"],
            }

        return results


if __name__ == "__main__":
    from data.fetch_mt5 import fetch_mt5_candles
    from data.fetch_binance import fetch_binance_candles
    from config.settings import FOREX_SYMBOLS, CRYPTO_SYMBOLS

    mt5_strategy = MomentumStrategy(data_fetcher=fetch_mt5_candles)
    forex_results = mt5_strategy.evaluate_universe(FOREX_SYMBOLS)

    print("=== Momentum Forex (ranking cross-sectional) ===")
    for symbol, r in sorted(forex_results.items(), key=lambda x: x[1]["strength"], reverse=True):
        print(f"  {symbol}: {r['direction']} (strength={r['strength']}, raw={r['raw_momentum']}%)")

    binance_strategy = MomentumStrategy(data_fetcher=fetch_binance_candles)
    crypto_results = binance_strategy.evaluate_universe(CRYPTO_SYMBOLS)

    print("\n=== Momentum Cripto (ranking cross-sectional) ===")
    for symbol, r in sorted(crypto_results.items(), key=lambda x: x[1]["strength"], reverse=True):
        print(f"  {symbol}: {r['direction']} (strength={r['strength']}, raw={r['raw_momentum']}%)")
