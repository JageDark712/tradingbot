#!/bin/bash

# Wrapper delgado que delega el arranque completo al módulo Python de bootstrap.
cd "$(dirname "$0")" || exit 1
[ -x "venv/bin/python" ] || {
  echo "❌ venv/bin/python no es ejecutable. Crea el entorno virtual primero."
  exit 1
}
venv/bin/python -m scanner.mt5_bootstrap --start
