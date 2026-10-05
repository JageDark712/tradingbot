"""
Scanner principal multi-estrategia (100% MT5/Exness): corre trend
following + momentum sobre todo el universo, las combina vía confluencia,
y calcula riesgo/tamaño de posición para los trades viables.
"""
import pandas as pd

from config.settings import (
    FOREX_SYMBOLS, CRYPTO_SYMBOLS, COMMODITY_SYMBOLS, ETF_SYMBOLS,
    CONFLUENCE_THRESHOLD,
)
from data.fetch_mt5 import fetch_mt5_candles
from strategies.trend_following import TrendFollowingStrategy
from strategies.momentum import MomentumStrategy
from regime.detector import RegimeDetector
from indicators.trend import calculate_atr
from confluence.scorer import combine_signals
from risk.engine import RiskEngine
from backtest.engine import ATR_SL_MULTIPLIER, RISK_REWARD_RATIO


def calculate_entry_and_stop(df_entry: pd.DataFrame, direction: str) -> dict:
    df = df_entry.copy()
    df["atr"] = calculate_atr(df)
    last = df.iloc[-1]

    entry_price = last["close"]
    atr = last["atr"]

    if direction == "alcista":
        sl_price = entry_price - atr * ATR_SL_MULTIPLIER
        tp_price = entry_price + atr * ATR_SL_MULTIPLIER * RISK_REWARD_RATIO
    else:
        sl_price = entry_price + atr * ATR_SL_MULTIPLIER
        tp_price = entry_price - atr * ATR_SL_MULTIPLIER * RISK_REWARD_RATIO

    return {
        "entry_price": round(float(entry_price), 5),
        "sl_price": round(float(sl_price), 5),
        "tp_price": round(float(tp_price), 5),
    }


def scan_category(symbols: list, category: str) -> list:
    """Evalúa trend following + momentum para una categoría de activos y combina vía confluencia."""
    trend_strategy = TrendFollowingStrategy(data_fetcher=fetch_mt5_candles)
    momentum_strategy = MomentumStrategy(data_fetcher=fetch_mt5_candles)
    regime_detector = RegimeDetector()

    results = []
    for symbol in symbols:
        try:
            # 1. Análisis de Régimen (Contexto de Mercado)
            df_context = fetch_mt5_candles(symbol, "H1", 200)
            regime_info = regime_detector.get_market_regime(df_context)
            market_regime = regime_info["regime"]

            trend_result = trend_strategy.evaluate(symbol)
            momentum_result = momentum_strategy.evaluate(symbol)

            momentum_strength = min(abs(momentum_result["raw_momentum"] or 0) / 10, 1.0)

            strategy_signals = {
                "trend_following": {
                    "direction": trend_result["direction"],
                    "strength": trend_result["strength"],
                },
                "momentum": {
                    "direction": momentum_result["direction"],
                    "strength": round(momentum_strength, 3),
                },
            }

            # Pasamos el régimen a la confluencia para permitir pesos dinámicos
            confluence = combine_signals(symbol, strategy_signals, regime=market_regime)

            if confluence.direction == "sin_senal":
                continue

            df_entry = fetch_mt5_candles(symbol, "H1")
            price_data = calculate_entry_and_stop(df_entry, confluence.direction)

            results.append({
                "symbol": symbol,
                "category": category,
                "direction": confluence.direction,
                "strength": confluence.confluence_score,
                "agreement": confluence.agreement,
                "regime": market_regime,
                "raw_momentum": momentum_result["raw_momentum"],
                **price_data,
            })
        except Exception as e:
            print(f"  [ERROR] {symbol}: {e}")

    return results


def run_full_scan() -> pd.DataFrame:
    """Corre el scan multi-estrategia sobre todo el universo, 100% vía MT5."""
    all_results = []

    universe = {
        "forex": FOREX_SYMBOLS,
        "commodity": COMMODITY_SYMBOLS,
        "index": ETF_SYMBOLS,
        "crypto": CRYPTO_SYMBOLS,
    }

    for category, symbols in universe.items():
        all_results.extend(scan_category(symbols, category))

    df = pd.DataFrame(all_results)
    if df.empty:
        return df
    df = df.sort_values("strength", ascending=False).reset_index(drop=True)
    return df


def get_viable_trades_with_risk(df: pd.DataFrame, account_balance: float, threshold: float = CONFLUENCE_THRESHOLD) -> pd.DataFrame:
    viable = df[df["strength"] >= threshold].copy()
    if viable.empty:
        return viable

    engine = RiskEngine(account_balance=account_balance)
    rows = []

    for _, row in viable.iterrows():
        risk_eval = engine.evaluate_trade(
            symbol=row["symbol"],
            category=row["category"],
            direction=row["direction"],
            signal_strength=row["strength"],
        )

        position_size = None
        if risk_eval["can_open"]:
            position_size = engine.calculate_position_size(
                entry_price=row["entry_price"],
                stop_loss_price=row["sl_price"],
                risk_amount=risk_eval["risk_amount"],
            )
            engine.open_trade(row["symbol"], row["category"], row["direction"], risk_eval["risk_pct"])

        rows.append({
            **row.to_dict(),
            "risk_pct": risk_eval["risk_pct"],
            "risk_amount": risk_eval["risk_amount"],
            "position_size": round(position_size, 6) if position_size else None,
            "can_open": risk_eval["can_open"],
        })

    return pd.DataFrame(rows)


if __name__ == "__main__":
    ACCOUNT_BALANCE = 500.0

    print("Corriendo scan multi-estrategia (100% MT5/Exness)...\n")
    all_results = run_full_scan()

    print("=== TODOS LOS RESULTADOS CON SEÑAL ===")
    cols = ["symbol", "category", "direction", "strength", "agreement"]
    print(all_results[cols].to_string(index=False) if not all_results.empty else "Sin señales.")

    final = get_viable_trades_with_risk(all_results, account_balance=ACCOUNT_BALANCE)
    print(f"\n=== TRADES VIABLES CON RIESGO (strength >= {CONFLUENCE_THRESHOLD}) ===")
    if final.empty:
        print("Ninguno supera el umbral en este momento.")
    else:
        cols = ["symbol", "category", "direction", "strength", "agreement",
                "entry_price", "sl_price", "tp_price", "risk_amount", "position_size", "can_open"]
        print(final[cols].to_string(index=False))
