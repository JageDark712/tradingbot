"""
Módulo de salud y auto-reparación para la conexión mt5linux.
Mantenido por compatibilidad; el código real ahora está en scanner.mt5_bootstrap.
"""
from scanner.mt5_bootstrap import (
    check_mt5_handshake,
    BootstrapConfig,
)

MT5LINUX_PORT = 18812
MT5LINUX_HOST = "127.0.0.1"


def check_and_repair_connection():
    """
    Verifica la conexión con el servidor mt5linux y repara fallos comunes.
    """
    print("🔍 Verificando salud de la conexión MT5...")
    config = BootstrapConfig()
    result = check_mt5_handshake(config)
    print(f"{'✅' if result.ok else '❌'} {result.message}")
    return result.ok