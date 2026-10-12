import sys, types, importlib.util
sys.path.insert(0, ".")
for name in ["mt5linux", "binance", "binance.client", "binance.enums", "dotenv"]:
    m = types.ModuleType(name); m.MetaTrader5 = object; m.Client = type("C", (), {}); m.load_dotenv = lambda *a, **k: None
    sys.modules[name] = m
import numpy as np, pandas as pd
import backtest.engine as new
spec = importlib.util.spec_from_file_location("engine_old", "tests/_engine_old_reference.py"); old = importlib.util.module_from_spec(spec); spec.loader.exec_module(old)

ok = []
def check(n, c, extra=""): ok.append(c); print("OK   " if c else "FALLA", n, extra)

# ---------- 1) regresión: con los parámetros viejos (SL 1.5, TP 4.5) da exactamente lo mismo ----------
rng = np.random.default_rng(3)
n = 6000
c = 100 * np.exp(np.cumsum(rng.normal(0, 0.004, n)))
sp = np.abs(rng.normal(0, 0.002, n)) * c
df = pd.DataFrame({"time": pd.date_range("2026-01-01", periods=n, freq="h"), "open": c, "high": c + sp, "low": c - sp, "close": c,
                   "atr": np.abs(rng.normal(0.6, 0.1, n)),
                   "signal": rng.choice(["alcista", "bajista", "sin_senal"], n, p=[0.04, 0.04, 0.92])})
t_old = old.simulate_trades(df)
t_new = new.simulate_trades(df, sl_mult=1.5, tp_mult=4.5)
cols = ["entry_time", "exit_time", "direction", "entry_price", "exit_price", "exit_reason", "pnl"]
same = (len(t_old) == len(t_new) > 100 and all((t_old[k].values == t_new[k].values).all() for k in ["entry_time","exit_time","direction","exit_reason","pnl"])
        and np.allclose(t_old.entry_price, t_new.entry_price, rtol=0, atol=1e-9) and np.allclose(t_old.exit_price, t_new.exit_price, rtol=0, atol=1e-9))
check("regresión: mismos trades que el motor anterior (SL 1.5 / TP 4.5)", same, f"({len(t_old)} trades; entrada, salida, motivo y PnL idénticos)")

# ---------- 2) casos armados a mano (SL 1.0 ATR, TP 1.5 ATR, ATR = 1.0, entrada = 100) ----------
def path(bars, signal_first="alcista"):
    rows = [dict(time=pd.Timestamp("2026-01-01"), open=100, high=100, low=100, close=100, atr=1.0, signal="sin_senal")]
    rows.append(dict(time=pd.Timestamp("2026-01-01 01:00"), open=100, high=100, low=100, close=100, atr=1.0, signal=signal_first))
    for k, (h, l, cl) in enumerate(bars, start=2):
        rows.append(dict(time=pd.Timestamp("2026-01-01") + pd.Timedelta(hours=k), open=cl, high=h, low=l, close=cl, atr=1.0, signal="sin_senal"))
    return pd.DataFrame(rows)
def sim(bars, **kw):
    kw.setdefault("sl_mult", 1.0); kw.setdefault("tp_mult", 1.5)
    return new.simulate_trades(path(bars, kw.pop("sig", "alcista")), **kw)

t = sim([(100.4, 99.8, 100.2), (101.6, 100.1, 101.5)])
check("compra: llega al TP 1.5 ATR  -> +1.5R", len(t) == 1 and t.pnl[0] == 1.5 and t.exit_reason[0] == "TP", f"| {t.pnl[0]}R")
t = sim([(100.4, 98.9, 99.2)])
check("compra: toca el SL 1.0 ATR   -> -1.0R", t.pnl[0] == -1.0 and t.exit_reason[0] == "SL")
t = sim([(100.3, 99.8, 100.1), (100.5, 99.9, 100.2), (100.7, 100.0, 100.6), (100.9, 100.2, 100.6)], max_hold_bars=3)
check("límite de tiempo: a las 3 velas cierra a mercado", t.exit_reason[0] == "tiempo" and t.bars_held[0] == 3 and abs(t.pnl[0] - 0.6) < 1e-9, f"| {t.exit_reason[0]}, {t.pnl[0]}R, {t.bars_held[0]} velas")
t = sim([(100.6, 100.0, 100.3), (100.4, 99.9, 100.1)], ladder=True)
check("SL escalonado: tras +0.5R el retroceso sale en breakeven (0R)", t.exit_reason[0] == "SL_escalonado" and t.pnl[0] == 0.0)
t = sim([(100.6, 100.0, 100.3), (100.4, 99.9, 100.1), (100.3, 99.5, 100.0)], ladder=False)
check("sin escalonado, ese mismo retroceso NO cierra (la posición sigue abierta)", len(t) == 0)
t = sim([(101.1, 100.0, 100.9), (100.9, 100.4, 100.6)], ladder=True)
check("SL escalonado: tras +1R el SL queda en +0.5R", t.exit_reason[0] == "SL_escalonado" and t.pnl[0] == 0.5, f"| {t.pnl[0]}R")
t = sim([(100.0, 98.4, 98.9), ], sig="bajista", sl_mult=1.0, tp_mult=1.5)
check("venta: TP 1.5 ATR abajo      -> +1.5R", len(t) == 1 and t.pnl[0] == 1.5 and t.exit_reason[0] == "TP", f"| {t.pnl[0]}R")
t = sim([(101.2, 99.9, 101.0)], sig="bajista")
check("venta: toca el SL arriba     -> -1.0R", t.pnl[0] == -1.0 and t.exit_reason[0] == "SL")
t = sim([(101.6, 100.1, 101.5)], cost_atr=0.1)
check("costo 0.1 ATR por trade resta 0.1R con SL=1 ATR", abs(t.pnl[0] - 1.4) < 1e-9, f"| {t.pnl[0]}R")
check("defaults de settings: SL 1.0 ATR, TP 1.5 ATR (ratio 1.5)", new.ATR_SL_MULTIPLIER == 1.0 and abs(new.RISK_REWARD_RATIO - 1.5) < 1e-9)
import config.settings as S
check("MULTI_TP_LEVELS final deriva de los multiplicadores", abs(S.MULTI_TP_LEVELS[2][0] - 1.5) < 1e-9, f"| {S.MULTI_TP_LEVELS}")
print(f"\nRESULTADO: {sum(ok)}/{len(ok)} OK"); sys.exit(0 if all(ok) else 1)
