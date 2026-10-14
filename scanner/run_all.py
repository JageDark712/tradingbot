"""
Orquestador único: levanta MT5 + servidor mt5linux (si no están corriendo)
y corre en paralelo el scanner/ejecución y el monitor de TPs escalonados.
"""
import sys
import threading
import time

from scanner.mt5_bootstrap import BootstrapConfig, ensure_mt5_ready, preflight_check
from scanner.run_live import run_continuous as run_scanner_loop
from execution.multi_tp_monitor import run_monitor as run_tp_monitor_loop


def ensure_mt5_running():
    print("Verificando MT5 y servidor mt5linux...")
    try:
        ensure_mt5_ready()
        print("MT5 y servidor listo.")
    except Exception as e:
        print(f"ERROR: {e}")
        sys.exit(1)


def run_scanner_thread(dry_run=False):
    try:
        run_scanner_loop(dry_run=dry_run)
    except Exception as e:
        print(f"\n[ERROR FATAL EN SCANNER] {e}")


def run_monitor_thread():
    try:
        run_tp_monitor_loop()
    except Exception as e:
        print(f"\n[ERROR FATAL EN MONITOR DE TPs] {e}")


def main():
    if "--check" in sys.argv:
        config = BootstrapConfig()
        code = preflight_check(config, start=True)
        sys.exit(code)

    ensure_mt5_running()

    dry_run = "--dry-run" in sys.argv

    print("\n" + "=" * 60)
    print("Iniciando scanner + monitor de TPs en paralelo")
    if dry_run:
        print("MODO DRY-RUN ACTIVO: no se enviarán órdenes reales")
    print("Presiona Ctrl+C para detener todo")
    print("=" * 60 + "\n")

    scanner_thread = threading.Thread(target=run_scanner_thread, args=(dry_run,), daemon=True)
    monitor_thread = threading.Thread(target=run_monitor_thread, daemon=True)
    scanner_thread.start()
    monitor_thread.start()

    try:
        while True:
            time.sleep(1)
            if not scanner_thread.is_alive() and not monitor_thread.is_alive():
                print("\nAmbos procesos terminaron inesperadamente. Saliendo.")
                sys.exit(1)
    except KeyboardInterrupt:
        print("\n\nDeteniendo todos los procesos...")
        sys.exit(0)


if __name__ == "__main__":
    main()
