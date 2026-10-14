"""
Gestiona la instancia única y persistente de mt5linux.MetaTrader5.
Usa el patrón Singleton para reutilizar la conexión RPyC al servidor Wine.

El servidor lo levanta scanner.mt5_bootstrap con:
    python -m mt5linux -w wine python -p 18812
"""
import time
import logging
from typing import Optional

from mt5linux import MetaTrader5

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ConnectionManager")

MT5LINUX_PORT = 18812
MT5LINUX_HOST = "127.0.0.1"


class MT5ConnectionManager:
    _instance = None
    _mt5: Optional[MetaTrader5] = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
        return cls._instance

    def reset(self):
        """Cierra y descarta la conexión actual."""
        self.close()

    def _connect_once(self) -> MetaTrader5:
        mt5 = MetaTrader5(host=MT5LINUX_HOST, port=MT5LINUX_PORT)
        info = mt5.terminal_info()
        if info is None:
            raise RuntimeError("terminal_info() devolvió None — el servidor no responde.")
        return mt5

    def get_connection(self, retries: int = 3) -> Optional[MetaTrader5]:
        """Devuelve una instancia viva de MetaTrader5, reconectando si hace falta."""
        if self._mt5 is not None and self._is_alive():
            return self._mt5

        if self._mt5 is not None:
            logger.warning("Conexión detectada como muerta. Reconectando...")
            self.reset()

        try:
            from scanner.mt5_bootstrap import ensure_mt5_ready

            ensure_mt5_ready()
        except Exception as exc:
            logger.warning("Bootstrap durante reconexión: %s", exc)

        for attempt in range(1, retries + 1):
            try:
                logger.info(
                    "Conectando a mt5linux en %s:%s (intento %s/%s)...",
                    MT5LINUX_HOST, MT5LINUX_PORT, attempt, retries,
                )
                mt5 = self._connect_once()
                info = mt5.terminal_info()
                logger.info("✅ Conexión establecida. Terminal: %s", getattr(info, "name", "MT5"))
                self._mt5 = mt5
                return self._mt5
            except Exception as exc:
                logger.error("❌ Intento %s fallido: %s", attempt, exc)
                self.reset()
                if attempt < retries:
                    time.sleep(2 ** attempt)

        logger.critical("No se pudo conectar con mt5linux tras varios intentos.")
        return None

    def _is_alive(self) -> bool:
        """Comprueba si la instancia sigue respondiendo."""
        try:
            return self._mt5 is not None and self._mt5.terminal_info() is not None
        except (EOFError, ConnectionResetError, ConnectionRefusedError, TimeoutError, OSError, AttributeError):
            return False
        except Exception:
            return False

    def close(self):
        """Cierra la conexión limpiamente."""
        if self._mt5 is not None:
            try:
                self._mt5.shutdown()
            except Exception:
                pass
            self._mt5 = None


connection_manager = MT5ConnectionManager()
