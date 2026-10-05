#!/bin/bash

WINE_BIN="/usr/bin/wine"
VENV_PYTHON="/home/jage/trading-scanner/venv/bin/python"
MT5_PATH="C:\Program Files\MetaTrader 5\terminal64.exe"
LOG_DIR="/home/jage/trading-scanner/logs"
mkdir -p "$LOG_DIR"

echo "Verificando terminal MT5..."
if ! pgrep -f "terminal64.exe" > /dev/null; then
    echo "MT5 no está corriendo. Abriendo..."
    setsid nohup "$WINE_BIN" "$MT5_PATH" > "$LOG_DIR/mt5.log" 2>&1 < /dev/null &
    echo "Esperando 15 segundos a que cargue..."
    sleep 15
else
    echo "MT5 ya está corriendo."
fi

echo "Verificando servidor mt5linux..."
if ! pgrep -f "mt5linux" > /dev/null; then
    echo "Servidor mt5linux no está corriendo. Levantando..."
    setsid nohup "$VENV_PYTHON" -m mt5linux -w "$WINE_BIN" python > "$LOG_DIR/mt5linux.log" 2>&1 < /dev/null &
    sleep 5
else
    echo "Servidor mt5linux ya está corriendo."
fi

echo "Listo."
