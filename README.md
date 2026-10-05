# Trading Scanner 📈

Sistema de trading algorítmico multi-activo y multi-estrategia diseñado para la detección de oportunidades en tiempo real, filtrado por confluencia y gestión de riesgo adaptativa.

## 🏗️ Arquitectura del Sistema

El proyecto sigue un pipeline lineal y modular para garantizar que solo las señales de alta probabilidad lleguen a la ejecución:

`Data` $\rightarrow$ `Market Regime` $\rightarrow$ `Strategies` $\rightarrow$ `Confluence` $\rightarrow$ `Risk` $\rightarrow$ `Execution` $\rightarrow$ `Monitoring`

### Componentes Principales:

- **`data/`**: Conectores para obtención de velas (candles) desde MetaTrader 5 (MT5) y Binance.
- **`regime/`**: Detector de régimen de mercado utilizando el **Exponente de Hurst** y **ADX** para clasificar el mercado en `TRENDING`, `RANGING` o `RANDOM`.
- **`indicators/`**: Cálculos técnicos personalizados (EMA, ADX, ATR).
- **`strategies/`**:
    - `TrendFollowingStrategy`: Análisis multi-timeframe (D1, H4, H1).
    - `MomentumStrategy`: Análisis de fuerza relativa y ranking cross-sectional.
- **`confluence/`**: Motor de scoring con **Pesos Dinámicos**. Ajusta la importancia de cada estrategia según el régimen detectado.
- **`risk/`**: Gestión de riesgo adaptativa, cálculo de tamaño de posición basado en Stop Loss y control de exposición agregada.
- **`execution/`**: Ejecutores para MT5 y Binance con soporte para Bracket Orders (SL/TP).
- **`monitoring/`**: Sistema de **Trailing Stop basado en ATR** y movimiento automático a Breakeven para proteger el capital.

## 🚀 Flujo de Trabajo

1. **Escaneo**: `scanner/run_scan.py` recorre el universo de símbolos.
2. **Contextualización**: Se detecta el régimen de mercado para cada activo.
3. **Evaluación**: Se ejecutan las estrategias y se combinan mediante la confluencia adaptativa.
4. **Filtrado**: El `RiskEngine` valida si el trade es viable según el balance de la cuenta y el riesgo permitido.
5. **Ejecución**: Se abre la posición en el broker.
6. **Seguimiento**: `execution/multi_tp_monitor.py` gestiona la salida dinámica del trade.

## 🛠️ Instalación y Uso

### Requisitos
- Python 3.10+
- MetaTrader 5 instalado (para Forex/Commodities)
- API Keys de Binance (para Cripto)

### Ejecución
Para correr un escaneo completo:
```bash
python scanner/run_scan.py
```

Para actualizar los stops de las posiciones abiertas:
```bash
python execution/multi_tp_monitor.py
```

## ⚙️ Configuración
Los parámetros globales (umbrales de ADX, pesos de estrategias, riesgo base por categoría) se encuentran en `config/settings.py`.
