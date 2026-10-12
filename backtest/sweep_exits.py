"""
Barrido de perfiles de salida sobre datos reales de MT5 (SL y TP en múltiplos de ATR(H1)).

Uso (desde la raíz, con MT5 y el servidor mt5linux corriendo):
    python -m backtest.sweep_exits                    # EURUSD
    python -m backtest.sweep_exits EURUSD GBPUSD BTCUSD

Compara, por símbolo:
  - SL en {0.75, 1.0, 1.5} ATR y TP en {1.0, 1.5, 2.0, 3.0, 4.5} ATR
  - con y sin SL escalonado (TP1 -> breakeven, TP2 -> SL en TP1)
  - con y sin límite de 5 horas (cierra a mercado)
Los resultados van en R (1R = lo que se arriesga). "Con costo" resta 0.05 ATR por trade
(spread + deslizamiento); con objetivos cortos el costo pesa mucho más.
"""
import itertools
import sys

import pandas as pd

from data.fetch_mt5 import fetch_mt5_candles
from backtest.engine import align_multi_timeframe, generate_signals, simulate_trades

SL_GRID = [0.75, 1.0, 1.5]
TP_GRID = [1.0, 1.5, 2.0, 3.0, 4.5]
HOLD_BARS = 5          # "4 o 5 horas" en velas H1
COST_ATR = 0.05
MIN_TRADES = 30        # con menos trades el profit factor no significa nada


def profit_factor(pnl: pd.Series) -> float:
    wins, losses = pnl[pnl > 0].sum(), -pnl[pnl <= 0].sum()
    return float(wins / losses) if losses > 0 else float("inf")


def evaluate(trades: pd.DataFrame, sl: float, tp: float, ladder: bool, hold) -> dict:
    cost_r = COST_ATR / sl                       # costo por trade expresado en R
    pnl_cost = trades["pnl"] - cost_r
    split = int(len(trades) * 0.7)
    return {
        "SL": sl, "TP": tp,
        "escalonado": "sí" if ladder else "no",
        "límite 5h": "sí" if hold else "no",
        "trades": len(trades),
        "TP≤5h %": round(100 * ((trades["exit_reason"] == "TP") & (trades["bars_held"] <= HOLD_BARS)).mean(), 1),
        "horas medias": round(float(trades["bars_held"].mean()), 1),
        "PF sin costo": round(profit_factor(trades["pnl"]), 2),
        "PF con costo": round(profit_factor(pnl_cost), 2),
        "PF 30% final": round(profit_factor(pnl_cost.iloc[split:]), 2),
        "neto R": round(float(pnl_cost.sum()), 1),
    }


def run_symbol(symbol: str) -> pd.DataFrame:
    print(f"\n{'=' * 78}\n{symbol}: descargando histórico...")
    d1 = fetch_mt5_candles(symbol, "D1", 1000)
    h4 = fetch_mt5_candles(symbol, "H4", 5000)
    h1 = fetch_mt5_candles(symbol, "H1", 20000)
    merged = generate_signals(align_multi_timeframe(d1, h4, h1))

    rows = []
    for sl, tp, ladder, hold in itertools.product(SL_GRID, TP_GRID, [False, True], [None, HOLD_BARS]):
        trades = simulate_trades(merged, sl_mult=sl, tp_mult=tp, ladder=ladder, max_hold_bars=hold)
        if len(trades) >= 2:
            rows.append(evaluate(trades, sl, tp, ladder, hold))
    return pd.DataFrame(rows)


def show(symbol: str, df: pd.DataFrame):
    valid = df[df["trades"] >= MIN_TRADES].sort_values("PF con costo", ascending=False)
    print(f"\n{symbol}: mejores 12 combinaciones (mínimo {MIN_TRADES} trades), ordenadas por PF con costo")
    print(valid.head(12).to_string(index=False))

    def ref(sl, tp, ladder, hold):
        m = df[(df.SL == sl) & (df.TP == tp) & (df.escalonado == ("sí" if ladder else "no")) & (df["límite 5h"] == ("sí" if hold else "no"))]
        return m
    print(f"\n{symbol}: perfiles de referencia")
    print(pd.concat([ref(1.5, 4.5, False, None).assign(perfil="anterior (1.5 / 4.5)"),
                     ref(1.0, 1.5, True, None).assign(perfil="corto (1.0 / 1.5, escalonado)"),
                     ref(1.0, 1.5, True, HOLD_BARS).assign(perfil="corto + límite 5 h")]).to_string(index=False))


if __name__ == "__main__":
    symbols = sys.argv[1:] or ["EURUSD"]
    for s in symbols:
        show(s, run_symbol(s))
    print("\nNotas: (1) los resultados están en R y los parámetros ganadores se eligen mirando el mismo histórico; "
          "confirma con la columna 'PF 30% final'. (2) Menos de 30 trades no se muestra: no es una muestra. "
          "(3) Con PF con costo < 1 el perfil pierde dinero una vez descontado el spread.")
