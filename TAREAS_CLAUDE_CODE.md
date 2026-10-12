# Tareas pendientes para Claude Code

Trabaja por fases, en orden. Lee primero `CLAUDE.md`, `README.md` (sobre todo "Limitaciones conocidas") y `CHANGELOG.md`.

## Reglas de trabajo

1. Después de cada tarea: corre las verificaciones, agrega una entrada a `CHANGELOG.md` (fecha, qué y por qué), actualiza `README.md` si cambia el comportamiento y haz **un commit por tarea** con mensaje claro. Haz push al terminar cada fase.
2. Antes y después de cada fase corre, desde la raíz: `python tests/verify_engine.py`, `python tests/verify_exits_and_selection.py` y `python tests/verify_scan_smoke.py`. Deben dar todo OK.
3. Cuenta **demo**. Nunca leas, muestres ni subas `.env`. No reintroduzcas Binance/OANDA en el flujo.
4. Todo cambio que altere **qué se opera** (pesos, umbral, límites, SL/TP) va detrás de una bandera en `config/settings.py` y con evidencia de backtest (números antes y después). El valor por defecto solo cambia si la evidencia lo respalda, y lo dices en el resumen de la fase. Si dudas, para y pregunta.
5. No cambies `CONFLUENCE_THRESHOLD` "para ver más trades". Si hace falta explorarlo, es un experimento de backtest, no un cambio de default.
6. Al final de cada fase entrega un resumen con: qué hiciste, cómo lo verificaste (comandos y resultado), números de backtest y qué queda pendiente o necesita mi decisión.

## Decisiones ya tomadas (no cambiar sin preguntarme)

- Todo por Exness/MT5 en cuenta demo; símbolos con sufijo `m`. Universo: 5 cripto (BTC, ETH, BNB, SOL, XRP), 10 forex, XAUUSD, USOIL, XNGUSD, US500, USTEC, US30, UK100.
- Señales: trend following multi-timeframe (D1 sesgo, H4 confirmación, H1 entrada; EMA 20/50 + ADX 14 ≥ 20) y momentum (ROC 20/60/120), combinados por confluencia con umbral 0.6.
- Se analiza todo el universo y luego se elige; si una orden falla se prueba la siguiente; un cupo solo se consume si la orden se ejecuta. Ciclo cada 15 min; monitor cada 30 s; un solo comando: `python -m scanner.run_all`.
- Ejecución automática con SL y TP dentro de la orden. **Lote fijo 0.01** con tope de riesgo por trade (`MAX_RISK_PER_TRADE_PCT`).
- Salida: SL escalonado (TP1 = 0.5R → breakeven; TP2 = 1R → SL en TP1) + trailing por ATR tras TP2. Sin cierres parciales (0.01 lotes no se divide). **No sustituyas `multi_tp_monitor.py` por un trailing puro.**
- Objetivo de duración: TP alcanzable en ~4–5 horas y, como máximo, 100–300 puntos. Perfil actual SL 1.0 / TP 1.5 ATR(H1), **sin validar**.
- Capital objetivo real: $50 (la demo tiene $500). Límites originalmente acordados: máx. 2 trades por categoría y 3% de riesgo agregado.

## Lecciones técnicas (no las rompas otra vez)

- `mt5linux`: pasa `float` nativos a `order_send` (un `numpy.float64` rompe la serialización). `copy_rates_range` falla: usa `copy_rates_from_pos` con N grande.
- `fetch_mt5_candles` agrega el sufijo `m`: pásale el símbolo estándar. Las posiciones de MT5 ya traen el símbolo con `m` (`ETHUSDm`).
- Retcodes vistos: 10018 mercado cerrado (forex en fin de semana), 10017 trading deshabilitado en ese símbolo (SOL/BNB/XRP en la demo), 10027 AutoTrading desactivado, 10016 stops inválidos, 10030 modo de llenado no soportado.
- AutoTrading debe estar activo en MT5 (se desactiva al reiniciarlo). Scripts siempre desde la raíz con `python -m ...`. El servidor `mt5linux` corre por Wine en el puerto 18812 y el terminal MT5 debe estar abierto y con sesión.
- Los hilos de `run_all.py` son `daemon` y hoy mueren en silencio si lanzan excepción.

---

## FASE 0 — Reconciliar el estado

Compara `git status`, `git log` y el contenido real con lo descrito aquí.

- Si existe `backtest/sweep_exits.py` y `config/settings.py` define `SL_ATR_MULTIPLIER`, el parche `todo-junto.patch` ya está aplicado: solo falta commit y push de lo que falte.
- Si no, aplícalo (`git apply --check` primero). Si hay conflictos, conserva SIEMPRE: el monitor combinado (SL escalonado + trailing con bucle `run_monitor()`), `FIXED_LOT`, `MAX_RISK_PER_TRADE_PCT`, `SL_ATR_MULTIPLIER`/`TP_ATR_MULTIPLIER` y `CONFLUENCE_THRESHOLD = 0.6`.
- Verifica que `python -m scanner.run_all` importa sin errores y que el monitor **corre en bucle** (la versión anterior hacía una sola pasada y terminaba).

## FASE 1 — Red de seguridad y medición (antes de cambiar nada)

1.1 **Suite pytest.** Convierte `tests/verify_*.py` a pytest conservando todos los escenarios, y agrega pruebas de: límites de `RiskEngine`, `confluence/scorer.py`, `position_tracker`. *Criterio:* `pytest` en verde.

1.2 **Modo `--dry-run`** en `run_live` y `run_all`: calcula y registra todo lo que haría sin llamar a `order_send`. *Criterio:* una prueba confirma que no se envía ninguna orden.

1.3 **Costos reales.** Lee el spread de cada símbolo (y comisión si aplica) y úsalo en el backtest (costo en R por símbolo) y como filtro en vivo `MAX_SPREAD_FRACTION_OF_TP` (omite la candidata si el spread supera esa fracción del TP, mostrando el motivo). Propón el valor por defecto a partir de datos. *Criterio:* el backtest reporta con y sin costos reales.

1.4 **Backtest de la estrategia completa.** Hoy solo cubre trend following en EURUSD. Reutiliza el MISMO código del vivo (strategies, scorer, regime) en vez de copiarlo; que cubra todo el universo; con costos; in-sample/out-of-sample y walk-forward. Compara cuatro configuraciones: (a) solo trend following, (b) trend + momentum con pesos fijos 0.6/0.4, (c) con la capa de régimen actual, (d) con el régimen corregido (cuando exista, ver 2.1). Guarda resultados en `reports/`. *Criterio:* tabla con profit factor, win rate, drawdown máximo en R, nº de trades y desglose por categoría.

1.5 **Barrido de salidas con datos reales.** Ejecuta `python -m backtest.sweep_exits` (MT5 abierto) en EURUSD, GBPUSD, USDJPY, XAUUSD, BTCUSD y US500. Reporta el mejor perfil por categoría con su profit factor fuera de muestra y con costos. **No cambies los defaults solo con esto:** propón y espera mi decisión.

## FASE 2 — Correcciones de la capa de señales (detrás de banderas)

2.1 **Régimen.** Mediciones previas: con ventana de 100 velas y lags hasta 49, un random walk sintético sale con Hurst ≈ 0.35 y se etiqueta 79% RANGING; las series con tendencia, 73% RANGING. Agrega la bandera `USE_REGIME_WEIGHTS` (default `False`). Corrige el estimador (ventana ≥ 400, lags máx. ~20) o sustitúyelo (variance ratio, DFA o Efficiency Ratio de Kaufman). Evalúalo con series sintéticas (random walk, persistente, anti-persistente) midiendo la tasa de error, y con el backtest A/B de 1.4. En RANGING no le des 80% de peso al momentum: es una estrategia de continuación. *Criterio:* tasa de error documentada y claramente menor que la actual; si no se logra, deja la capa desactivada y documéntalo.

2.2 **Momentum comparable entre categorías.** La fuerza actual es `min(|ROC%|/10, 1)`: satura en cripto y casi nunca pasa de 0.4 en forex, así que el forex casi nunca califica. Normaliza por categoría (ranking dentro de la categoría, o ROC / volatilidad) con la bandera `MOMENTUM_NORMALIZATION = "category" | "legacy"`. *Criterio:* medianas de fuerza similares por categoría y un scan con datos reales donde el forex pueda calificar cuando corresponda.

2.3 **Señal parcial.** Una sola estrategia activa multiplica el score por 0.6 y el umbral es 0.6, así que solo pasa cuando satura. Rediséñalo (umbral relativo o penalización distinta) con evidencia de backtest.

2.4 **Límites de riesgo.** Restaura `MAX_TRADES_PER_CATEGORY = 2` y `MAX_AGGREGATE_RISK = 0.03` (valores acordados; Claude Code los había subido a 5 y 5%). Agrega un límite por correlación (`MAX_CORRELATED_SAME_DIRECTION`: máx. N posiciones en la misma dirección dentro de un grupo correlacionado, estimado con correlación rolling de retornos H1). *Criterio:* pruebas.

2.5 **Herramienta de capital.** `tools/min_risk_report.py`: para cada símbolo, el riesgo en dinero y en % que implica el lote mínimo con el SL vigente, y qué símbolos pasan el tope con capital de $50, $100 y $500. *Criterio:* tabla impresa.

## FASE 3 — Protecciones para operar en automático

3.1 **Circuit breaker** (`risk/circuit_breaker.py`): pérdida diaria máxima, pérdida semanal máxima (el plan original era 4× el riesgo por operación) y N pérdidas consecutivas, tras lo cual no se abren posiciones nuevas hasta el siguiente periodo. Estado persistente y calculado desde `history_deals_get` de MT5. Parámetros en settings. *Criterio:* pruebas con MT5 simulado y mensaje claro en el ciclo.

3.2 **Verificación de arranque** en `run_all`: AutoTrading activo (`terminal_info().trade_allowed`) y cuenta **demo**. Si es cuenta real, aborta salvo `ALLOW_LIVE_ACCOUNT = True` (default `False`).

3.3 **Resiliencia de `run_all`:** reinicia el scanner o el monitor si su hilo muere por excepción (con límite de reintentos y log) y que `start_mt5.sh` no tenga rutas fijas de usuario.

3.4 **Mercado cerrado:** detecta sesión cerrada (ticks desactualizados / `trade_mode`) antes de enviar órdenes, en lugar de depender del retcode 10018.

3.5 **Reconciliación al arrancar:** posiciones abiertas sin registro en `position_tracker` (manuales o previas) se registran con su riesgo original si tienen SL, o se marcan "no gestionadas"; limpia los tickets cerrados.

## FASE 4 — Registro y seguimiento

4.1 **Diario** en SQLite o CSV dentro de `logs/` (ignorado por git): por ciclo (señales, régimen, scores, candidatas, decisión y motivo), por orden (precio pedido vs. llenado, spread) y por cierre (motivo, R realizado, horas abierta).

4.2 **`tools/report_live.py`:** resumen diario/semanal con nº de trades, win rate, profit factor, R neto, horas medias hasta el TP, % que llegó al TP en ≤ 5 h y comparación con el backtest.

## FASE 5 — Más estrategias (solo con la Fase 1 terminada)

5.1 **Registro de estrategias** (`strategies/registry.py`): `scan_category` y el scorer no deben nombrar estrategias; agregar una = una clase + su peso en settings. *Criterio:* mover trend y momentum al registro sin cambiar resultados (las verificaciones siguen igual).

5.2 **Mean reversion** (RSI(2), Bollinger o Connors en H1, con filtro de tendencia de un timeframe mayor), pensada para objetivos de 4–5 h. Bandera `ENABLE_MEAN_REVERSION = False`. Solo se activa si el profit factor fuera de muestra y con costos es > 1 en varios símbolos.

5.3 **Variante rápida de trend following** (H4 sesgo, H1 confirmación, M15 entrada) como experimento para horizontes de 4–5 h; compárala con la actual usando el barrido.

5.4 **Pairs / stat arb:** solo evaluar viabilidad (cointegración de pares correlacionados en H1) y reportar. No implementes la ejecución sin mi aprobación (requiere dos patas).

5.5 **Filtro de EMA 200** como componente opcional de confirmación. Volume Profile: descártalo salvo que muestres que el volumen de tick del CFD aporta información.

## FASE 6 — Limpieza

6.1 Mueve el código heredado (Binance/OANDA) a `legacy/` o elimínalo, y actualiza `requirements.txt` y el README.
6.2 Quita `signals/` y `.vscode/` del repo y ajusta `.gitignore` (`logs/`, `reports/` si procede).
6.3 Mantén `README.md` y `CHANGELOG.md` al día.

## No hacer

- No subir el lote ni quitar el tope `MAX_RISK_PER_TRADE_PCT`.
- No operar en cuenta real.
- No cambiar la lógica del monitor sin evidencia.
- No dar por buena una estrategia con menos de ~30 trades ni sin resultados fuera de muestra y con costos.
