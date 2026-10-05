"""
Detector de Régimen de Mercado: Identifica si el mercado está en tendencia, en rango o en ruido.
Utiliza el Exponente de Hurst y el ADX para clasificar el comportamiento del precio.
"""
import pandas as pd
import numpy as np
from indicators.trend import calculate_adx
from config.settings import ADX_THRESHOLD

class RegimeDetector:
    def __init__(self, hurst_period: int = 100, adx_threshold: float = ADX_THRESHOLD):
        self.hurst_period = hurst_period
        self.adx_threshold = adx_threshold

    def _calculate_hurst(self, series: pd.Series) -> float:
        """
        Calcula el Exponente de Hurst simplificado para detectar persistencia o reversión.
        H < 0.5: Mean-reverting (Rango)
        H = 0.5: Random Walk (Ruido)
        H > 0.5: Trending (Tendencia)
        """
        if len(series) < self.hurst_period:
            return 0.5

        # Tomamos la ventana más reciente
        data = series.tail(self.hurst_period).values

        # Calculamos los logs de los precios para analizar el crecimiento
        # Evitamos ceros o negativos
        l_data = np.log(data) if np.all(data > 0) else data

        # Cálculo simplificado de Hurst mediante la diferencia de rangos
        # (R/S Analysis simplificado para eficiencia en tiempo real)
        lags = np.arange(2, self.hurst_period // 2)
        tau = []

        for lag in lags:
            # Diferencias la serie por el lag
            diffs = np.abs(l_data[lag:] - l_data[:-lag])
            # Calculamos la desviación estándar de las diferencias
            tau.append(np.std(diffs))

        # El log de la desviación estándar vs log del lag da la pendiente (Hurst)
        # x = log(lags), y = log(tau)
        reg = np.polyfit(np.log(lags), np.log(tau), 1)
        return reg[0]

    def get_market_regime(self, df: pd.DataFrame) -> dict:
        """
        Analiza el DataFrame y clasifica el régimen actual.

        Args:
            df: DataFrame con columna 'close'

        Returns:
            dict con 'regime' ("TRENDING", "RANGING", "RANDOM") y 'score' (valor de Hurst)
        """
        if df is None or len(df) < self.hurst_period:
            return {"regime": "RANDOM", "score": 0.5, "reason": "Insuficientes datos"}

        # 1. Calcular Hurst
        hurst = self._calculate_hurst(df["close"])

        # 2. Calcular ADX para confirmar fuerza
        adx_data = calculate_adx(df)
        last_adx = adx_data["adx"].iloc[-1]

        # Lógica de clasificación
        # Caso 1: Tendencia fuerte (Hurst alto + ADX alto)
        if hurst > 0.55 and last_adx >= self.adx_threshold:
            regime = "TRENDING"
            reason = f"Persistencia detectada (H={hurst:.2f}) y ADX fuerte ({last_adx:.2f})"

        # Caso 2: Rango / Medio-reversión (Hurst bajo)
        elif hurst < 0.45:
            regime = "RANGING"
            reason = f"Reversión a la media detectada (H={hurst:.2f})"

        # Caso 3: Ruido / Indeterminado
        else:
            regime = "RANDOM"
            reason = f"Comportamiento aleatorio o débil (H={hurst:.2f}, ADX={last_adx:.2f})"

        return {
            "regime": regime,
            "score": round(float(hurst), 3),
            "adx": round(float(last_adx), 2) if not pd.isna(last_adx) else None,
            "reason": reason
        }

if __name__ == "__main__":
    # Test rápido
    from data.fetch_mt5 import fetch_mt5_candles

    symbol = "EURUSD"
    df = fetch_mt5_candles(symbol, "H1", 200)
    detector = RegimeDetector()
    result = detector.get_market_regime(df)
    print(f"Régimen para {symbol}: {result}")
