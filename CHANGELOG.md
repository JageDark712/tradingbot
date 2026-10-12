# Registro de cambios

Formato: fecha, quién (chat / Claude Code), archivos tocados y por qué.

## 2026-10-06 — chat — Arranque del sistema, lote fijo y monitor combinado
- `config/settings.py`: agrega `FIXED_LOT=0.01`, `MAX_RISK_PER_TRADE_PCT=0.03` y `ATR_TRAILING_MULTIPLIER=2.0`. El monitor importaba esta última y no existía: el ImportError impedía arrancar `run_all.py`.
- `execution/multi_tp_monitor.py`: reescrito. SL escalonado (TP1=0.5R → breakeven, TP2=1R → SL en TP1) y trailing 2×ATR(H1) tras TP2; el TP final de 3R sigue en la orden. Corrige: faltaba `run_monitor()`; doble sufijo `m` al pedir velas (`ETHUSDmm`); el breakeven usaba el SL actual y podía aflojar un stop ya subido por el trailing. Sin cierres parciales (lote 0.01).
- `execution/mt5_executor.py`: agrega `check_symbol_tradable` y `calculate_fixed_volume`; los errores de cierre/modificación muestran el retcode real; el cierre parcial prueba otros modos de llenado.
- `scanner/run_live.py`: lote fijo con tope de riesgo por trade; verifica que el símbolo sea operable antes de enviar la orden; imprime las señales de todas las categorías antes de aplicar el umbral.
- `README.md` y `requirements.txt`: reescritos para reflejar el flujo real (solo MT5) y las limitaciones medidas.
- Sin tocar, por decisión del usuario (solo hacer que arranque): régimen, pesos de confluencia y límites de riesgo de Claude Code (`MAX_TRADES_PER_CATEGORY=5`, `MAX_AGGREGATE_RISK=5%`). Ver "Limitaciones conocidas" en el README.

## 2026-10-08 — chat — Salidas cortas (objetivo en ~4–5 horas)
- `config/settings.py`: nuevos `SL_ATR_MULTIPLIER=1.0` y `TP_ATR_MULTIPLIER=1.5` (antes fijos en `backtest/engine.py`: 1.5 y 4.5). El TP final de `MULTI_TP_LEVELS` se deriva de ellos.
- `backtest/engine.py`: toma los multiplicadores de settings; `simulate_trades` y `run_backtest` aceptan `sl_mult`, `tp_mult`, `max_hold_bars`, `ladder` y `cost_atr`. Con los valores anteriores reproduce idénticos los trades (probado con 300).
- `backtest/sweep_exits.py` (nuevo): compara perfiles de SL/TP, con y sin SL escalonado, con y sin límite de 5 h, con y sin costo.
- `scanner/run_live.py` y `execution/mt5_executor.py`: las candidatas muestran SL y TP en puntos.
- Motivo: con SL 1.5 ATR y TP 4.5 ATR, el TP se alcanzaba en ≤ 5 h solo el 0.7% de las veces en un mercado sin ventaja (simulación): era un objetivo de varios días.
- Pendiente: validar el perfil corto con `backtest.sweep_exits` sobre datos reales y varios símbolos antes de darlo por bueno.

## 2026-10-08 — chat — Reconciliación con `559da77`, verificaciones y tareas pendientes
- El monitor que dejó Claude Code en `559da77` (`run_monitor()` hacía una sola pasada y terminaba) se sustituye por el monitor combinado con bucle. Con `run_all`, el monitor moría tras un ciclo y nadie gestionaba el SL.
- `config/settings.py`: una sola definición de `ATR_TRAILING_MULTIPLIER` (la de `559da77` y la de este parche coincidían en 2.0).
- `tests/verify_*.py` (nuevos): motor de backtest (incluye regresión contra `tests/_engine_old_reference.py`), monitor y selección con un MT5 simulado, y escaneo completo sintético.
- `docs/TAREAS_CLAUDE_CODE.md` (nuevo): tareas pendientes por fases.
2026-10-12: Aplicación del parche todo-junto.patch para reconciliar el estado del proyecto (monitor combinado, gestión de riesgo y parámetros de confluencia).
