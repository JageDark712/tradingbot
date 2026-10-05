"""
Orquestador único: levanta MT5 + servidor mt5linux (si no están corriendo)
y corre en paralelo el scanner/ejecución y el monitor de TPs escalonados.
"""
import os
import socket
import subprocess
import sys
import threading
import time

from scanner.run_live import run_continuous as run_scanner_loop
from execution.multi_tp_monitor import run_monitor as run_tp_monitor_loop

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
MT5_SERVER_HOST = "127.0.0.1"
MT5_SERVER_PORT = 18812


def wait_for_port(host: str, port: int, timeout: int = 90) -> bool:
    """Espera hasta que el servidor mt5linux acepte conexiones."""
    start = time.time()
    while time.time() - start < timeout:
        try:
            with socket.create_connection((host, port), timeout=2):
                return True
        except OSError:
            time.sleep(2)
    return False


def ensure_mt5_running():
    print("Verificando MT5 y servidor mt5linux...")
    subprocess.run(
        ["bash", os.path.join(PROJECT_DIR, "start_mt5.sh")],
        cwd=PROJECT_DIR,
        timeout=180,
    )
    print(f"Esperando a que el servidor responda en el puerto {MT5_SERVER_PORT}...")
    if not wait_for_port(MT5_SERVER_HOST, MT5_SERVER_PORT):
        print("ERROR: el servidor mt5linux no respondió. Revisa logs/mt5linux.log")
        sys.exit(1)
    print("Servidor listo.")


def run_scanner_thread():
    try:
        run_scanner_loop()
    except Exception as e:
        print(f"\n[ERROR FATAL EN SCANNER] {e}")


def run_monitor_thread():
    try:
        run_tp_monitor_loop()
    except Exception as e:
        print(f"\n[ERROR FATAL EN MONITOR DE TPs] {e}")


def main():
    ensure_mt5_running()

    print("\n" + "=" * 60)
    print("Iniciando scanner + monitor de TPs en paralelo")
    print("Presiona Ctrl+C para detener todo")
    print("=" * 60 + "\n")

    scanner_thread = threading.Thread(target=run_scanner_thread, daemon=True)
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
