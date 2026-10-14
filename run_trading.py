#!/usr/bin/env python
"""
Punto de entrada único: arranque completo + ejecución real sin preguntas.

Uso:
  python run_trading.py [--dry-run]    # Inicia MT5 y corre scanner en modo simulación
  python run_trading.py --check        # Solo diagnóstico por capas
"""
import sys
import os

# Garantizar que el proyecto está en el path
project_dir = os.path.dirname(os.path.abspath(__file__))
if project_dir not in sys.path:
    sys.path.insert(0, project_dir)

from scanner.mt5_bootstrap import BootstrapConfig, ensure_mt5_ready, preflight_check
from scanner.run_live import run_continuous


def main():
    dry_run = "--dry-run" in sys.argv

    if "--check" in sys.argv:
        # Solo diagnosticar, no ejecutar
        config = BootstrapConfig()
        code = preflight_check(config, start=True)
        sys.exit(code)

    print("\n" + "=" * 70)
    print("🤖 TRADING SCANNER - ARRANQUE AUTOMÁTICO")
    print("=" * 70)

    # 1. Asegurar que MT5 + servidor están listos
    print("\n[1/3] Verificando MT5 y servidor mt5linux...")
    try:
        ensure_mt5_ready()
        print("✅ MT5 y servidor operativos.")
    except Exception as e:
        print(f"❌ Error: {e}")
        sys.exit(1)

    # 2. Mostrar modo
    print("\n[2/3] Configurando modo de ejecución...")
    if dry_run:
        print("⚠️  MODO DRY-RUN: no se enviarán órdenes reales (para pruebas)")
    else:
        print("🟢 MODO REAL: ejecutando órdenes en cuenta demo")

    # 3. Iniciar scanner continuo
    print("\n[3/3] Iniciando scanner continuo...")
    print("-" * 70)

    try:
        run_continuous(dry_run=dry_run)
    except KeyboardInterrupt:
        print("\n\n[DETENIDO] Presionaste Ctrl+C. Saliendo...")
        sys.exit(0)
    except Exception as e:
        print(f"\n❌ Error fatal: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
