"""
Unified Backtest Engine: Replicates the live pipeline over historical data.
Pipeline: Data -> Regime -> Strategies -> Confluence -> Risk -> Execution.
"""
import pandas as pd
import numpy as np
from typing import List, Dict, Any, Optional
from dataclasses import dataclass

from config.settings import (
    TIMEFRAMES, SL_ATR_MULTIPLIER, TP_ATR_MULTIPLIER,
    MULTI_TP_LEVELS, MAX_AGGREGATE_RISK, MAX_TRADES_PER_CATEGORY,
    CONFLUENCE_THRESHOLD
)
from indicators.trend import calculate_atr
from regime.detector import RegimeDetector

@dataclass
class TradeResult:
    symbol: str
    entry_time: pd.Timestamp
    exit_time: pd.Timestamp
    direction: str
    entry_price: float
    exit_price: float
    exit_reason: str
    pnl_r: float
    bars_held: int

class UnifiedBacktestEngine:
    def __init__(self, cost_atr: float = 0.0):
        """
        Args:
            cost_atr: Fixed cost per trade as a multiple of ATR (spread + slippage).
        """
        self.cost_atr = cost_atr
        self.regime_detector = RegimeDetector()

    def simulate_trade_logic(self,
                             symbol: str,
                             df_h1: pd.DataFrame,
                             signals_series: pd.DataFrame) -> List[TradeResult]:
        """
        Simulates trades for a single symbol given a series of confluences.
        """
        trades = []
        in_position = False
        entry_i = sign = entry = sl = tp = risk0 = atr = None

        sl_mult = SL_ATR_MULTIPLIER
        tp_mult = TP_ATR_MULTIPLIER
        lvl1, lvl2 = MULTI_TP_LEVELS[0][0], MULTI_TP_LEVELS[1][0]

        times = df_h1["time"].to_numpy()
        highs = df_h1["high"].to_numpy(float)
        lows = df_h1["low"].to_numpy(float)
        closes = df_h1["close"].to_numpy(float)
        atrs = calculate_atr(df_h1).to_numpy(float)

        directions = signals_series["direction"].to_numpy()
        scores = signals_series["confluence_score"].to_numpy()

        for i in range(1, len(df_h1)):
            if not in_position:
                if directions[i] in ("alcista", "bajista") and scores[i] >= CONFLUENCE_THRESHOLD:
                    sign = 1 if directions[i] == "alcista" else -1
                    entry = closes[i]
                    atr = atrs[i]
                    risk0 = atr * sl_mult
                    sl = sl0 = entry - sign * risk0
                    tp = entry + sign * atr * tp_mult
                    entry_i = i
                    in_position = True
                continue

            if sign == 1:
                hit_sl, hit_tp = lows[i] <= sl, highs[i] >= tp
            else:
                hit_sl, hit_tp = highs[i] >= sl, lows[i] <= tp

            reason = exit_price = None
            if hit_sl:
                reason, exit_price = ("SL" if sl == sl0 else "SL_escalonado"), sl
            elif hit_tp:
                reason, exit_price = "TP", tp

            if reason:
                raw_pnl = (exit_price - entry) * sign
                pnl_r = (raw_pnl - self.cost_atr * atr) / risk0 if risk0 > 0 else 0
                trades.append(TradeResult(
                    symbol=symbol,
                    entry_time=times[entry_i],
                    exit_time=times[i],
                    direction="alcista" if sign == 1 else "bajista",
                    entry_price=entry,
                    exit_price=exit_price,
                    exit_reason=reason,
                    pnl_r=float(pnl_r),
                    bars_held=i - entry_i
                ))
                in_position = False
            else:
                favorable = (highs[i] - entry) if sign == 1 else (entry - lows[i])
                new_sl = None
                if favorable >= lvl2 * risk0:
                    new_sl = entry + sign * lvl1 * risk0
                elif favorable >= lvl1 * risk0:
                    new_sl = entry
                if new_sl is not None and ((sign == 1 and new_sl > sl) or (sign == -1 and new_sl < sl)):
                    sl = new_sl

        return trades
