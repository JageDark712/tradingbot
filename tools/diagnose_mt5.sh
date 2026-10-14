#!/bin/bash
# Diagnóstico por capas de la conexión Python <-> MT5 (Linux + Wine + mt5linux).
#
# Uso, desde una terminal NORMAL del sistema (la integrada de VSCode-Flatpak no ve wine):
#     cd ~/trading-scanner && ./tools/diagnose_mt5.sh
#
# Se detiene en la primera capa que falla y deja las versiones en docs/ENTORNO.md.
[ -n "$BASH_VERSION" ] || { echo "Ejecútalo con bash: ./tools/diagnose_mt5.sh (no con sh)"; exit 1; }
cd "$(dirname "$0")/.." || exit 1
export WINEDEBUG=-all
PORT=18812
VENV_PY="venv/bin/python"
ENV_FILE="docs/ENTORNO.md"
mkdir -p docs logs
F=$(printf '\140\140\140')

G='\033[32m'; R='\033[31m'; Y='\033[33m'; N='\033[0m'
ok()    { echo -e "${G}[OK]${N}     $1"; }
warn()  { echo -e "${Y}[AVISO]${N}  $1"; }
layer() { echo; echo "=== Capa $1 ==="; }
fail()  {
  echo -e "${R}[FALLA]${N}  $1"
  echo "          -> $2"
  echo
  echo "Se detiene aquí. Arregla esta capa y vuelve a correr el script."
  echo "Pégame esta salida completa si no sabes cómo seguir."
  exit 1
}
add() { echo "$1" >> "$ENV_FILE"; }

{
  echo "# Entorno (capturado $(date '+%Y-%m-%d %H:%M'))"
  echo
  echo "- Sistema: $(lsb_release -ds 2>/dev/null) | kernel $(uname -r)"
} > "$ENV_FILE"

# ---------------------------------------------------------------- Capa 0
layer "0: Wine"
command -v wine >/dev/null || fail "wine no está en el PATH" \
  "¿estás en la terminal integrada de VSCode (Flatpak)? Abre una terminal normal. Si no está instalado: sudo apt install wine wine64"
WINE_V=$(wine --version 2>/dev/null)
[ -n "$WINE_V" ] || fail "wine no responde" "prueba 'wine --version' a mano"
ok "Wine: $WINE_V"
add "- Wine: $WINE_V"

# ---------------------------------------------------------------- Capa 1
layer "1: entorno virtual de Linux (venv)"
[ -x "$VENV_PY" ] || fail "no existe $VENV_PY" "créalo: python3.10 -m venv venv && source venv/bin/activate && pip install -r requirements.txt"
VPY_V=$($VENV_PY --version 2>&1) || fail "el venv no arranca ($VPY_V)" \
  "su Python base ya no existe (el sistema lo actualizó o lo quitó). Recrea el venv: rm -rf venv && python3.10 -m venv venv"
ok "venv: $VPY_V  (base: $(readlink -f $VENV_PY))"
IMPORT_ERR=$($VENV_PY -c "import pandas, numpy, rpyc, mt5linux" 2>&1) || fail "faltan o fallan paquetes en el venv" \
  "$(echo "$IMPORT_ERR" | tail -n 1)  ->  pip install -r requirements.txt && pip install mt5linux==0.1.9 --no-deps"
RPYC_LINUX=$($VENV_PY -c "import importlib.metadata as m; print(m.version('rpyc'))")
PANDAS_V=$($VENV_PY -c "import pandas; print(pandas.__version__)")
NUMPY_V=$($VENV_PY -c "import numpy; print(numpy.__version__)")
ok "rpyc $RPYC_LINUX | pandas $PANDAS_V | numpy $NUMPY_V"
add "- Python (venv): $VPY_V"
add ""
add "## pip freeze (Linux, venv)"
add "$F"
$VENV_PY -m pip freeze >> "$ENV_FILE" 2>/dev/null
add "$F"

# ---------------------------------------------------------------- Capa 2
layer "2: Python dentro de Wine"
WPY_V=$(timeout 90 wine python --version 2>&1 | tr -d '\r' | tail -n 1)
echo "$WPY_V" | grep -q "^Python" || fail "'wine python' no responde (${WPY_V:-sin salida})" \
  "el Python de Windows no está en este prefijo de Wine (¿se recreó o actualizó Wine?). Reinstala: wine python-3.9.0-amd64.exe  (marca Add to PATH)"
ok "Python en Wine: $WPY_V"
WINE_PKGS=$(timeout 120 wine python -c "import MetaTrader5, importlib.metadata as m; print(MetaTrader5.__version__, m.version('rpyc'))" 2>&1 | tr -d '\r' | tail -n 1)
echo "$WINE_PKGS" | grep -Eq '^[0-9][0-9.]* [0-9][0-9.]*$' || fail "faltan paquetes en el Python de Wine (${WINE_PKGS:-sin salida})" \
  "wine python -m pip install MetaTrader5 rpyc==$RPYC_LINUX"
MT5PY_V=${WINE_PKGS% *}
RPYC_WINE=${WINE_PKGS#* }
ok "paquete MetaTrader5 $MT5PY_V | rpyc (Wine) $RPYC_WINE"
[ "$RPYC_LINUX" = "$RPYC_WINE" ] || fail "rpyc distinto: Linux $RPYC_LINUX vs Wine $RPYC_WINE" \
  "deben ser idénticos (si no, la conexión se cuelga con 'result expired'). Iguala: wine python -m pip install rpyc==$RPYC_LINUX"
add ""
add "- Python (Wine): $WPY_V | paquete MetaTrader5 $MT5PY_V"
add ""
add "## pip freeze (Python de Wine)"
add "$F"
timeout 120 wine python -m pip freeze 2>/dev/null >> "$ENV_FILE"
add "$F"

# ---------------------------------------------------------------- Capa 3
layer "3: terminal MT5"
pgrep -f "terminal64.exe" >/dev/null || fail "MT5 no está corriendo" \
  "./start_mt5.sh   (o a mano: wine \"C:\\Program Files\\MetaTrader 5\\terminal64.exe\"; luego espera ~15 s)"
ok "terminal64.exe está corriendo"

# ---------------------------------------------------------------- Capa 4
layer "4: servidor mt5linux"
pgrep -f "mt5linux" >/dev/null || fail "el servidor mt5linux no está corriendo" \
  "./start_mt5.sh   (o a mano: $VENV_PY -m mt5linux -w wine python)"
(exec 3<>/dev/tcp/127.0.0.1/$PORT) 2>/dev/null || fail "el proceso existe pero nada escucha en el puerto $PORT" \
  "mira el log: tail -n 30 logs/mt5linux.log ; si hay un error de rpyc o de import, repite la capa 2"
ok "el servidor responde en 127.0.0.1:$PORT"

# ---------------------------------------------------------------- Capa 5
layer "5: conexión real con MT5 (broker, cuenta, precios, velas)"
OUT=$(timeout 90 $VENV_PY - << 'PYEOF' 2>&1
import sys
from mt5linux import MetaTrader5
mt5 = MetaTrader5()
if not mt5.initialize():
    print("initialize() devolvió False:", mt5.last_error()); sys.exit(2)
ti = mt5.terminal_info()
print("build del terminal:", ti.build, "| API:", mt5.version())
print("terminal conectado al broker:", ti.connected, "| AutoTrading:", ti.trade_allowed)
if not ti.connected:
    sys.exit(3)
ai = mt5.account_info()
if ai is None:
    print("sin cuenta activa:", mt5.last_error()); sys.exit(4)
print("cuenta:", ai.login, "|", ai.server, "| balance", ai.balance, ai.currency, "| tipo:", "demo" if ai.trade_mode == 0 else "NO es demo")
mt5.symbol_select("EURUSDm", True)
rates = mt5.copy_rates_from_pos("EURUSDm", mt5.TIMEFRAME_H1, 0, 50)
if rates is None or len(rates) == 0:
    print("sin velas de EURUSDm:", mt5.last_error()); sys.exit(5)
print("velas H1 de EURUSDm recibidas:", len(rates))
sys.exit(0 if ti.trade_allowed else 6)
PYEOF
)
RC=$?
echo "$OUT" | sed 's/^/          /'
add ""
add "## MT5"
add "$F"
add "$OUT"
add "$F"
case $RC in
  0) ok "conexión completa: broker, cuenta, velas y AutoTrading" ;;
  6) warn "conecta y trae datos, pero AutoTrading está DESACTIVADO (botón rojo en MT5). Sin eso las órdenes fallan con 10027." ;;
  2) fail "initialize() falló" "el terminal está abierto pero no responde a la API. Cierra MT5, corre pkill -f mt5linux y vuelve a ./start_mt5.sh" ;;
  3) fail "el terminal no está conectado al servidor del broker" \
       "mira la esquina inferior derecha de MT5: si dice 'No connection' o 'Invalid account', inicia sesión otra vez. Las cuentas demo pueden caducar: si no entra, crea una nueva en Exness y úsala" ;;
  4) fail "MT5 no tiene una cuenta activa" "inicia sesión en la ventana de MT5 (Archivo > Iniciar sesión)" ;;
  5) fail "conecta pero no llegan velas" "el símbolo EURUSDm no existe en esta cuenta o el mercado/servidor no responde; abre 'Observación de mercado' y busca EURUSDm" ;;
  124) fail "la conexión se colgó (timeout de 90 s)" \
       "casi siempre es un desajuste de versiones de rpyc o un servidor mt5linux colgado: pkill -f mt5linux && ./start_mt5.sh y repite" ;;
  *) fail "error inesperado (código $RC)" "pega la salida completa" ;;
esac

echo
echo "Versiones guardadas en $ENV_FILE"
exit 0
