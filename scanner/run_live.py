"""
Orquestador de ejecución en vivo. Flujo por ciclo:
  1) Analiza TODO el universo y rankea las candidatas.
  2) Carga en el motor de riesgo las posiciones reales ya abiertas.
  3) Recorre las candidatas en orden; un cupo solo se consume si la orden
     realmente se ejecuta. Si una falla (mercado cerrado, rechazo), pasa a la siguiente.
"""
import sys
import time
import datetime
import traceback

from config.settings import (
    FOREX_SYMBOLS, CRYPTO_SYMBOLS, COMMODITY_SYMBOLS, ETF_SYMBOLS,
    CONFLUENCE_THRESHOLD,
)
from scanner.run_scan import run_full_scan
from risk.engine import RiskEngine
from execution.mt5_executor import (
    execute_mt5_order, get_open_mt5_positions, get_effective_balance,
    calculate_mt5_volume, estimate_position_open_risk,
)

SCAN_INTERVAL_MINUTES = 15

CATEGORY_BY_SYMBOL = {}
for _cat, _syms in {
    "forex": FOREX_SYMBOLS, "crypto": CRYPTO_SYMBOLS,
    "commodity": COMMODITY_SYMBOLS, "index": ETF_SYMBOLS,
}.items():
    for _s in _syms:
        CATEGORY_BY_SYMBOL[_s] = _cat


def to_standard_symbol(mt5_symbol: str) -> str:
    return mt5_symbol[:-1] if mt5_symbol.endswith("m") else mt5_symbol


def rank_candidates(df):
    """Ordena por fuerza; desempata por coincidencia entre estrategias y luego por momentum."""
    df = df.copy()
    df["agreement_rank"] = df["agreement"].map({"full": 0, "partial": 1}).fillna(2)
    if "raw_momentum" in df.columns:
        df["abs_momentum"] = df["raw_momentum"].abs().fillna(0)
    else:
        df["abs_momentum"] = 0.0
    df = df.sort_values(
        ["strength", "agreement_rank", "abs_momentum"],
        ascending=[False, True, False],
    )
    return df.reset_index(drop=True)


def build_engine_from_open_positions(balance: float):
    """Carga las posiciones reales abiertas en MT5 al motor de riesgo."""
    engine = RiskEngine(account_balance=balance)
    open_symbols = set()

    for pos in get_open_mt5_positions():
        symbol = to_standard_symbol(pos["symbol"])
        category = CATEGORY_BY_SYMBOL.get(symbol)
        if category is None:
            continue
        direction = "alcista" if pos["type"] == 0 else "bajista"
        risk_amount = estimate_position_open_risk(pos)
        risk_pct = risk_amount / balance if balance > 0 else 0.0
        engine.open_trade(symbol, category, direction, risk_pct)
        open_symbols.add(symbol)

    return engine, open_symbols


def select_and_execute(candidates, engine, open_symbols, balance):
    executed, skipped, failed = [], [], []

    for _, row in candidates.iterrows():
        symbol, category, direction = row["symbol"], row["category"], row["direction"]

        if symbol in open_symbols:
            print(f"  [YA ABIERTA] {symbol}")
            continue

        risk_pct = engine.calculate_trade_risk_pct(category, row["strength"])
        can_open, reason = engine.can_open_trade(category, risk_pct)
        if not can_open:
            print(f"  [OMITIDO] {symbol}: {reason}")
            skipped.append(symbol)
            continue

        sizing = calculate_mt5_volume(
            symbol, direction, row["entry_price"], row["sl_price"], balance * risk_pct
        )
        if sizing["volume"] is None:
            print(f"  [OMITIDO] {symbol}: {sizing['reason']}")
            skipped.append(symbol)
            continue

        result = execute_mt5_order(
            symbol=symbol, direction=direction, volume=sizing["volume"],
            sl_price=row["sl_price"], tp_price=row["tp_price"],
        )

        if result["success"]:
            engine.open_trade(symbol, category, direction, sizing["actual_risk"] / balance)
            open_symbols.add(symbol)
            executed.append(symbol)
            print(f"  [✓ EJECUTADO] {symbol} {direction} | lotes={sizing['volume']} | riesgo=${sizing['actual_risk']:.2f}")
        else:
            err = str(result.get("error", ""))
            tag = "MERCADO CERRADO" if ("Market closed" in err or "10018" in err) else "FALLÓ"
            print(f"  [{tag}] {symbol}: {err} -> se prueba con la siguiente candidata")
            failed.append(symbol)

    print(f"\nResumen: {len(executed)} ejecutadas, {len(skipped)} omitidas, {len(failed)} fallidas")
    return executed


def run_one_cycle():
    print(f"\n{'=' * 60}")
    print(f"Ciclo de scan: {datetime.datetime.now():%Y-%m-%d %H:%M:%S}")
    print("=" * 60)

    balance = get_effective_balance()
    print(f"Capital operativo: ${balance:.2f}")

    all_results = run_full_scan()
    if all_results.empty:
        print("Sin señales en este ciclo.")
        return

    candidates = rank_candidates(all_results)
    candidates = candidates[candidates["strength"] >= CONFLUENCE_THRESHOLD]

    if candidates.empty:
        print(f"{len(all_results)} señales, ninguna supera el umbral ({CONFLUENCE_THRESHOLD}).")
        return

    print(f"\n{len(candidates)} candidata(s) en orden de prioridad:")
    print(candidates[["symbol", "category", "direction", "strength", "agreement"]].to_string(index=False))

    engine, open_symbols = build_engine_from_open_positions(balance)
    print(f"\nPosiciones ya abiertas: {sorted(open_symbols) or 'ninguna'}")
    print("\nSeleccionando y ejecutando:")
    select_and_execute(candidates, engine, open_symbols, balance)


def run_continuous():
    print(f"Iniciando scanner continuo (intervalo: {SCAN_INTERVAL_MINUTES} min)")
    while True:
        try:
            run_one_cycle()
        except Exception as e:
            print(f"\n[ERROR EN EL CICLO] {e}")
            traceback.print_exc()
        print(f"\nEsperando {SCAN_INTERVAL_MINUTES} minutos hasta el próximo ciclo...")
        time.sleep(SCAN_INTERVAL_MINUTES * 60)


if __name__ == "__main__":
    if "--once" in sys.argv:
        run_one_cycle()
    else:
        run_continuous()
