# Trading Scanner

Scanner multi-activo y multi-estrategia: busca setups en forex, cripto, materias primas e índices, los combina por confluencia y opera en **cuenta demo de Exness (MT5)**.

> Proyecto en desarrollo. Lo único validado con backtest es trend following en EURUSD. Ver [Limitaciones conocidas](#limitaciones-conocidas).

## Pipeline

`data → indicators → strategies → regime → confluence → risk → execution → monitor`

| Carpeta | Qué hace |
|---|---|
| `data/` | Velas desde MT5 vía `mt5linux` (`fetch_mt5.py`). `fetch_binance*.py` es código heredado, fuera del flujo actual. |
| `indicators/` | EMA, ADX, ATR (`trend.py`) y ROC (`momentum.py`). |
| `strategies/` | `trend_following.py`: D1 sesgo, H4 confirmación, H1 entrada (solo hay señal si los tres coinciden). `momentum.py`: ROC 20/60/120 en D1. |
| `regime/` | Detector Hurst + ADX (TRENDING / RANGING / RANDOM). **Experimental.** |
| `confluence/` | Combina las estrategias en un score 0–1. Pesos 0.6/0.4 por defecto, o dinámicos según el régimen. Una sola estrategia activa multiplica el score por 0.6; si se contradicen, el score es 0; en RANDOM multiplica además por 0.7. |
| `risk/` | `RiskEngine`: límites de trades por categoría y de riesgo agregado, y sizing adaptativo (solo si `FIXED_LOT = None`). |
| `execution/` | `mt5_executor.py`: órdenes con SL y TP en la misma orden, lote fijo, verificación de símbolo operable. `multi_tp_monitor.py`: gestión de salida. `position_tracker.py`: registro local del riesgo original de cada posición. `binance_*`: heredado. |
| `scanner/` | `run_scan.py` analiza todo el universo; `run_live.py` es el ciclo (analiza, rankea, ejecuta); `run_all.py` lo levanta todo con un solo comando. |
| `backtest/` | Motor in-sample / out-of-sample (`engine.py`, `metrics.py`, `run_backtest_eurusd.py`). |
| `config/` | Parámetros (`settings.py`) y mapeo de símbolos (`symbols.py`, sufijo `m` de Exness). |

## Reglas de operación vigentes

- **Universo:** 5 cripto (BTC, ETH, BNB, SOL, XRP), 10 forex, XAUUSD, USOIL, XNGUSD y 4 índices (US500, USTEC, US30, UK100). En MT5 cada símbolo lleva el sufijo `m`.
- **Selección:** se analiza TODO el universo, se rankea por score (desempate: coincidencia completa de estrategias y luego momentum) y se opera en ese orden. Entra si el score es ≥ `CONFLUENCE_THRESHOLD` (0.6). Si una orden falla (mercado cerrado, símbolo no operable) pasa a la siguiente; un cupo solo se consume si la orden se ejecuta. El ciclo se repite cada 15 minutos.
- **Stop y objetivo:** SL inicial a `SL_ATR_MULTIPLIER` × ATR(H1) (1.0) y TP final a `TP_ATR_MULTIPLIER` × ATR(H1) (1.5), ambos dentro de la orden. Es un objetivo corto, pensado para cumplirse en ~4–5 horas; el perfil anterior era 1.5 / 4.5 (swing de varios días). El ciclo imprime el SL y el TP de cada candidata en puntos.
- **Tamaño:** lote fijo `FIXED_LOT = 0.01`. El trade se omite si ese lote arriesga más de `MAX_RISK_PER_TRADE_PCT` (3%) del capital operativo. Con `FIXED_LOT = None` se usa el sizing por riesgo adaptativo.
- **Límites:** `MAX_TRADES_PER_CATEGORY` y `MAX_AGGREGATE_RISK` en `config/settings.py`.
- **Salida (monitor, cada 30 s):** al llegar a TP1 (0.5R) el SL pasa a breakeven; al llegar a TP2 (1R) pasa al nivel de TP1; después hay trailing a 2 × ATR(H1) (`ATR_TRAILING_MULTIPLIER`). El SL nunca se afloja. Con el TP final a 1.5R el trailing casi no llega a actuar: el SL escalonado hace el trabajo. No hay cierres parciales: con 0.01 lotes la posición no se puede dividir.
- **Capital:** `OPERATING_CAPITAL = None` usa el balance real de la cuenta; `50.0` simula una cuenta de $50.

## Cómo correrlo (Linux Mint + Wine + mt5linux)

Requisitos: Python 3.10 en un venv, MT5 de Exness instalado en Wine con sesión demo iniciada, y **AutoTrading activado** (se desactiva cada vez que se reinicia MT5).

```bash
pip install -r requirements.txt
pip install mt5linux==0.1.9 --no-deps
```

Siempre desde la raíz del proyecto y con `-m`:

```bash
./start_mt5.sh                          # abre MT5 y el servidor mt5linux (ajusta las rutas del script a tu usuario)
python -m scanner.run_live --once       # un solo ciclo; puede abrir órdenes en la demo
python -m scanner.run_all               # todo junto: MT5 + scanner + monitor
python -m execution.multi_tp_monitor    # solo el monitor
python -m backtest.run_backtest_eurusd  # backtest de trend following en EURUSD
python -m backtest.sweep_exits EURUSD GBPUSD  # compara perfiles de SL/TP/escalonado/límite de 5 h con tus datos
```

Para dejarlo corriendo todo el día usa `tmux` y evita que el equipo se suspenda. Si el mercado de un símbolo está cerrado, ese ciclo lo omite y lo reintenta en el siguiente.

`.env` solo lo usa el código heredado de Binance; el flujo con MT5 no lo necesita. Nunca se sube al repo.

## Verificaciones (sin MT5, con datos sintéticos)

```bash
python tests/verify_engine.py               # motor de backtest: regresión y casos con resultado conocido
python tests/verify_exits_and_selection.py  # monitor (SL escalonado / trailing) y selección de órdenes con un MT5 simulado
python tests/verify_scan_smoke.py           # escaneo completo del universo, de punta a punta
```

## Limitaciones conocidas

Medido el 2026-10-06 con datos sintéticos y con las lecturas reales de los scans:

1. **Régimen sesgado.** Con ventana de 100 velas y lags hasta 49, el Hurst de un random walk sintético sale ≈ 0.35 (debería ser ≈ 0.5) y el 79% se etiqueta RANGING. En RANGING los pesos pasan a 0.2 tendencia / 0.8 momentum. No está validado con backtest.
2. **Momentum con escala de cripto.** La fuerza es `min(|ROC%| / 10, 1)`: en cripto satura, en forex rara vez pasa de 0.4. Con umbral 0.6, el forex casi nunca califica.
3. **Señal parcial limitada.** Una sola estrategia activa tiene tope 0.6, así que solo pasa el umbral si satura en 1.0.
4. **Backtest acotado.** Solo trend following en EURUSD con el perfil anterior (SL 1.5 / TP 4.5 ATR; 3 años, H1, sin fricción): profit factor 1.12 in-sample y 1.39 out-of-sample, win rate 27–32%, 273 trades, drawdown máximo −24R in-sample. No cubre confluencia, régimen, la salida escalonada ni otros símbolos.
5. **Trailing casi inerte.** Con el TP final a 1.5R, el trailing de 2×ATR no supera al SL escalonado antes de que la orden cierre en el TP.
6. **Correlación.** Con `MAX_TRADES_PER_CATEGORY` alto pueden abrirse varias posiciones cripto que son casi una sola apuesta.
7. **Capital pequeño.** Con $50, el lote mínimo de BTCUSD arriesgaba ~13% con el SL anterior (1.5 ATR); con SL 1.0 ATR baja a ~9% y el tope del 3% lo sigue omitiendo.
8. **Perfil corto sin validar.** En un mercado sin ventaja (random walk simulado), un TP a 4.5 ATR se alcanza en ≤ 5 h el 0.7% de las veces y uno a 1.5 ATR el ~31% (con SL 1.0). Con SL 1.0 / TP 1.5 hace falta ganar ≥ 40% de los trades para no perder, y el spread pesa más cuanto más cerca está el TP. Medir con `backtest.sweep_exits` antes de confiar.

## Colaboración

- `CLAUDE.md`: reglas de trabajo para Claude Code.
- `docs/TAREAS_CLAUDE_CODE.md`: tareas pendientes por fases, decisiones ya tomadas y lecciones técnicas.
- `CHANGELOG.md`: registro de cambios (fecha, quién, archivos y motivo).
- `tools/export_snapshot.sh`: genera `snapshot.md` con el estado del proyecto para compartirlo en otros chats.
