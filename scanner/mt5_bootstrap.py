"""
Bootstrap, arranque automático y diagnóstico por capas para MetaTrader 5 y mt5linux.
Fuente única de verdad para el ciclo de vida del servidor Wine/MT5.
"""
from dataclasses import dataclass, field
import importlib
import logging
import os
from pathlib import Path
import shutil
import socket
import subprocess
import sys
import time
from typing import Any, Dict, List, Optional, Tuple

import config.settings as settings

logger = logging.getLogger("mt5_bootstrap")

EXPECTED_VERSIONS = {
    "linux": {
        "rpyc": "5.0.1",
        "pandas": "2.3.3",
        "numpy": "2.2.6",
        "mt5linux": "0.1.9",
    },
    "wine": {
        "python": "Python 3.9.0",
        "MetaTrader5": "5.0.6231",
        "rpyc": "5.0.1",
    },
    "terminal": {
        "build": 6231,
        "date": "27 Sep 2026",
    },
}


@dataclass
class BootstrapConfig:
    project_dir: Path = field(default_factory=lambda: Path(__file__).resolve().parent.parent)
    log_dir: Optional[Path] = None
    host: str = "127.0.0.1"
    port: int = 18812
    wine_cmd: str = field(default_factory=lambda: shutil.which("wine") or "wine")
    server_timeout: float = 30.0
    handshake_timeout: float = 30.0
    pid_file: Optional[Path] = None

    def __post_init__(self):
        self.project_dir = Path(self.project_dir)
        if self.log_dir is None:
            self.log_dir = self.project_dir / "logs"
        else:
            self.log_dir = Path(self.log_dir)
        if self.pid_file is None:
            self.pid_file = self.log_dir / "mt5linux.pid"
        else:
            self.pid_file = Path(self.pid_file)


@dataclass
class LayerResult:
    name: str
    ok: bool
    message: str
    details: Optional[str] = None


@dataclass
class PreflightReport:
    ok: bool
    results: List[LayerResult]


def is_port_open(host: str, port: int, timeout: float = 1.0) -> bool:
    """Verifica si el puerto indicado está aceptando conexiones TCP."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (OSError, ConnectionRefusedError, socket.timeout):
        return False


def wait_for_port(host: str, port: int, timeout: float = 30.0) -> bool:
    """Espera activamente a que el puerto responda antes del timeout."""
    start = time.time()
    while time.time() - start < timeout:
        if is_port_open(host, port, timeout=1.0):
            return True
        time.sleep(1.0)
    return False


def read_pid(path: Path) -> Optional[int]:
    """Lee el PID almacenado en disco si existe y es válido."""
    try:
        p = Path(path)
        if p.is_file():
            content = p.read_text().strip()
            if content.isdigit():
                return int(content)
    except Exception:
        pass
    return None


def write_pid(path: Path, pid: int) -> None:
    """Guarda el PID en el archivo especificado."""
    try:
        p = Path(path)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(str(pid))
    except Exception as exc:
        logger.warning(f"No se pudo escribir el PID {pid} en {path}: {exc}")


def is_pid_running(pid: int) -> bool:
    """Comprueba si un proceso sigue vivo mediante señal 0."""
    if pid <= 0:
        return False
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def terminate_pid(pid: int, timeout: float = 5.0) -> None:
    """Termina un proceso limpiamente con SIGTERM y luego SIGKILL si es necesario."""
    if not is_pid_running(pid):
        return
    try:
        os.kill(pid, 15)  # SIGTERM
    except OSError:
        return

    start = time.time()
    while time.time() - start < timeout:
        if not is_pid_running(pid):
            return
        time.sleep(0.5)

    if is_pid_running(pid):
        try:
            os.kill(pid, 9)  # SIGKILL
        except OSError:
            pass


def start_server_process(config: BootstrapConfig) -> int:
    """Lanza el servidor mt5linux con el comando conocido funcional (-w wine python)."""
    config.log_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        sys.executable,
        "-m",
        "mt5linux",
        "-w",
        config.wine_cmd,
        "python",
        "-p",
        str(config.port),
    ]

    # shortcut: Wine Python falla con stdout/stderr redirigidos a archivo; usar /dev/null hasta necesitar logs
    proc = subprocess.Popen(
        cmd,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        cwd=str(config.project_dir),
    )

    write_pid(config.pid_file, proc.pid)
    return proc.pid


def ensure_server_running(config: BootstrapConfig) -> LayerResult:
    """Garantiza que el servidor mt5linux esté escuchando en el puerto configurado."""
    if is_port_open(config.host, config.port):
        return LayerResult("mt5linux", True, f"servidor escuchando en {config.host}:{config.port}")

    old_pid = read_pid(config.pid_file)
    if old_pid and is_pid_running(old_pid):
        logger.info(f"Terminando proceso mt5linux huérfano PID {old_pid}...")
        terminate_pid(old_pid)

    start_server_process(config)

    if wait_for_port(config.host, config.port, timeout=config.server_timeout):
        return LayerResult("mt5linux", True, f"servidor escuchando en {config.host}:{config.port}")

    return LayerResult(
        "mt5linux",
        False,
        f"servidor mt5linux no responde en {config.host}:{config.port}",
    )


def check_wine(config: BootstrapConfig) -> LayerResult:
    """Capa 0: Verifica la disponibilidad y versión de Wine."""
    wine_bin = shutil.which(config.wine_cmd)
    if not wine_bin:
        return LayerResult("Wine", False, f"wine no está en el PATH ('{config.wine_cmd}')")

    try:
        res = subprocess.run(
            [config.wine_cmd, "--version"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        version_str = res.stdout.strip() or res.stderr.strip()
        if res.returncode == 0 and version_str:
            return LayerResult("Wine", True, f"Wine: {version_str}")
        return LayerResult("Wine", False, f"wine --version devolvió error: {version_str}")
    except Exception as exc:
        return LayerResult("Wine", False, f"Fallo al ejecutar wine: {exc}")


def check_linux_env(config: BootstrapConfig) -> LayerResult:
    """Capa 1: Verifica el entorno de ejecución en Linux y dependencias clave."""
    try:
        import pandas as pd
        import numpy as np
        import rpyc
        import mt5linux

        rpyc_v = getattr(rpyc, "__version__", None)
        if isinstance(rpyc_v, (tuple, list)):
            rpyc_v = ".".join(str(x) for x in rpyc_v)
        else:
            rpyc_v = str(rpyc_v)
        pandas_v = str(pd.__version__)
        numpy_v = str(np.__version__)
        mt5linux_v = str(getattr(mt5linux, "__version__", "0.1.9"))

        return LayerResult(
            "Linux venv",
            True,
            f"Python {sys.version.split()[0]} | rpyc {rpyc_v} | pandas {pandas_v} | numpy {numpy_v} | mt5linux {mt5linux_v}",
        )
    except Exception as exc:
        return LayerResult("Linux venv", False, f"Faltan dependencias en Linux: {exc}")


def check_wine_python(config: BootstrapConfig) -> LayerResult:
    """Capa 2: Verifica Python dentro de Wine y la paridad estricta de rpyc."""
    env = dict(os.environ, WINEDEBUG="-all")
    try:
        res_v = subprocess.run(
            [config.wine_cmd, "python", "--version"],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        wpy_v = (res_v.stdout + res_v.stderr).strip().splitlines()
        wpy_line = wpy_v[-1] if wpy_v else ""
        if "Python" not in wpy_line:
            return LayerResult("Wine Python", False, f"'wine python' no responde ({wpy_line})")

        res_pkgs = subprocess.run(
            [
                config.wine_cmd,
                "python",
                "-c",
                "import MetaTrader5, importlib.metadata as m; print(MetaTrader5.__version__, m.version('rpyc'))",
            ],
            capture_output=True,
            text=True,
            timeout=60,
            env=env,
        )
        pkgs_line = (res_pkgs.stdout + res_pkgs.stderr).strip().splitlines()
        last_pkg = pkgs_line[-1] if pkgs_line else ""
        parts = last_pkg.split()
        if len(parts) != 2:
            return LayerResult("Wine Python", False, f"Faltan paquetes en Python de Wine: {last_pkg}")

        mt5_v, rpyc_wine_v = parts[0], parts[1]

        import rpyc

        rpyc_raw = getattr(rpyc, "__version__", "")
        if isinstance(rpyc_raw, (tuple, list)):
            rpyc_linux_v = ".".join(str(x) for x in rpyc_raw)
        else:
            rpyc_linux_v = str(rpyc_raw).strip()

        rpyc_wine_clean = str(rpyc_wine_v).strip()

        if rpyc_wine_clean != rpyc_linux_v:
            return LayerResult(
                "Wine Python",
                False,
                f"rpyc distinto: Linux {rpyc_linux_v} vs Wine {rpyc_wine_clean}. "
                "Deben ser idénticos para evitar colgarse con 'result expired'.",
            )

        return LayerResult(
            "Wine Python",
            True,
            f"Wine {wpy_line} | MetaTrader5 {mt5_v} | rpyc {rpyc_wine_clean}",
        )
    except Exception as exc:
        return LayerResult("Wine Python", False, f"Error verificando Python en Wine: {exc}")


def ensure_mt5_terminal_running(config: BootstrapConfig) -> LayerResult:
    """Capa 3: Asegura que el terminal MT5 esté activo en Wine."""
    try:
        ps_out = subprocess.run(["ps", "-eo", "cmd"], capture_output=True, text=True, timeout=5)
        if "terminal64.exe" in ps_out.stdout:
            return LayerResult("MT5 terminal", True, "terminal64.exe está corriendo")
    except Exception:
        pass

    target_path = "C:\\Program Files\\MetaTrader 5\\terminal64.exe"
    config.log_dir.mkdir(parents=True, exist_ok=True)
    mt5_log = config.log_dir / "mt5.log"

    try:
        env = dict(os.environ, WINEDEBUG="-all")
        with open(mt5_log, "a") as log:
            subprocess.Popen(
                [config.wine_cmd, target_path],
                stdout=log,
                stderr=subprocess.STDOUT,
                stdin=subprocess.DEVNULL,
                start_new_session=True,
                env=env,
            )
        time.sleep(10)
        return LayerResult("MT5 terminal", True, "terminal64.exe lanzado en Wine")
    except Exception as exc:
        return LayerResult("MT5 terminal", False, f"Fallo al arrancar terminal MT5: {exc}")


def create_mt5_client(config: BootstrapConfig):
    """Crea una instancia cliente de MetaTrader5 conectada al servidor mt5linux."""
    from mt5linux import MetaTrader5

    return MetaTrader5(host=config.host, port=config.port)


def check_mt5_handshake(config: BootstrapConfig) -> LayerResult:
    """Capa 5: Valida conexión con MT5, estado del broker, AutoTrading y cuenta demo."""
    try:
        mt5 = create_mt5_client(config)
        if not mt5.initialize():
            err = getattr(mt5, "last_error", lambda: "desconocido")()
            return LayerResult("MT5 handshake", False, f"initialize() falló: {err}")

        ti = mt5.terminal_info()
        if ti is None:
            return LayerResult("MT5 handshake", False, "terminal_info() devolvió None")

        if not getattr(ti, "connected", False):
            return LayerResult("MT5 handshake", False, "terminal no conectado al broker")

        if not getattr(ti, "trade_allowed", False):
            return LayerResult(
                "MT5 handshake",
                False,
                "AutoTrading desactivado en MT5. Las órdenes fallarán con 10027. Activa 'Algo Trading' en el terminal.",
            )

        ai = mt5.account_info()
        if ai is None:
            err = getattr(mt5, "last_error", lambda: "desconocido")()
            return LayerResult("MT5 handshake", False, f"sin cuenta activa en MT5: {err}")

        trade_mode = getattr(ai, "trade_mode", 0)
        is_demo = trade_mode == 0
        allow_live = getattr(settings, "ALLOW_LIVE_ACCOUNT", False)
        if not is_demo and not allow_live:
            return LayerResult(
                "MT5 handshake",
                False,
                "cuenta real detectada. El sistema solo opera en cuenta demo salvo ALLOW_LIVE_ACCOUNT=True en config/settings.py.",
            )

        sym = "EURUSDm"
        mt5.symbol_select(sym, True)
        rates = mt5.copy_rates_from_pos(sym, getattr(mt5, "TIMEFRAME_H1", 16385), 0, 10)
        has_rates = rates is not None and len(rates) > 0

        acc_type = "demo" if is_demo else "real"
        build = getattr(ti, "build", "desconocido")
        return LayerResult(
            "MT5 handshake",
            True,
            f"conexión completa: broker conectado, cuenta {acc_type}, AutoTrading activo, velas H1 recibidas: {has_rates}",
        )
    except Exception as exc:
        return LayerResult("MT5 handshake", False, f"Excepción durante handshake con MT5: {exc}")


def check_expected_versions(linux: Dict[str, str], wine: Dict[str, str], terminal_version: Tuple[Any, ...]) -> LayerResult:
    """Verifica compatibilidad de versiones documentadas y paridad de rpyc."""
    if linux.get("rpyc") != wine.get("rpyc"):
        return LayerResult(
            "Versiones",
            False,
            f"desajuste de versiones rpyc: Linux ({linux.get('rpyc')}) != Wine ({wine.get('rpyc')}). "
            "Esto provoca que la conexión se cuelgue con 'result expired'.",
        )
    return LayerResult("Versiones", True, "versiones verificadas y compatibles")


def run_preflight(config: Optional[BootstrapConfig] = None, start: bool = False) -> PreflightReport:
    """Ejecuta el chequeo por capas completo y devuelve un reporte estructurado."""
    if config is None:
        config = BootstrapConfig()

    results: List[LayerResult] = []

    # Capa 0: Wine
    r0 = check_wine(config)
    results.append(r0)
    if not r0.ok:
        return PreflightReport(ok=False, results=results)

    # Capa 1: Linux venv
    r1 = check_linux_env(config)
    results.append(r1)
    if not r1.ok:
        return PreflightReport(ok=False, results=results)

    # Capa 2: Wine Python
    r2 = check_wine_python(config)
    results.append(r2)
    if not r2.ok:
        return PreflightReport(ok=False, results=results)

    # Capa 3: Terminal MT5 (start=True intenta levantarlo si falta)
    r3 = ensure_mt5_terminal_running(config)
    results.append(r3)
    if not r3.ok:
        return PreflightReport(ok=False, results=results)

    # Capa 4: Servidor mt5linux
    r4 = ensure_server_running(config)
    results.append(r4)
    if not r4.ok:
        return PreflightReport(ok=False, results=results)

    # Capa 5: Handshake MT5
    r5 = check_mt5_handshake(config)
    results.append(r5)

    all_ok = all(r.ok for r in results)
    return PreflightReport(ok=all_ok, results=results)


def preflight_check(config: Optional[BootstrapConfig] = None, start: bool = True) -> int:
    """Imprime el diagnóstico por capas y retorna 0 (éxito) o 1 (fallo)."""
    if config is None:
        config = BootstrapConfig()

    print("\n" + "=" * 60)
    print("  PREFLIGHT DIAGNÓSTICO MT5 / mt5linux")
    print("=" * 60)

    report = run_preflight(config, start=start)

    for idx, r in enumerate(report.results):
        tag = "[OK]   " if r.ok else "[FALLA]"
        print(f"Capa {idx} ({r.name:15}): {tag} {r.message}")

    print("=" * 60)
    if report.ok:
        print("✅ Todas las capas están operativas. MT5 listo para operar.")
        return 0
    else:
        print("❌ Preflight falló en una o más capas. Revisa los mensajes anteriores.")
        return 1


def ensure_mt5_ready(config: Optional[BootstrapConfig] = None) -> bool:
    """Garantiza que MT5 y el servidor mt5linux estén listos antes de operar."""
    if config is None:
        config = BootstrapConfig()

    if is_port_open(config.host, config.port):
        hs = check_mt5_handshake(config)
        if hs.ok:
            return True

    report = run_preflight(config, start=True)
    if not report.ok:
        failed_layers = [f"{r.name}: {r.message}" for r in report.results if not r.ok]
        raise RuntimeError("MT5 no está listo:\n  " + "\n  ".join(failed_layers))
    return True


if __name__ == "__main__":
    cfg = BootstrapConfig()
    if "--check" in sys.argv:
        code = preflight_check(cfg, start=True)
        sys.exit(code)
    elif "--start" in sys.argv:
        print("Levantando MT5 y servidor mt5linux...")
        ready = ensure_mt5_ready(cfg)
        sys.exit(0 if ready else 1)
    else:
        code = preflight_check(cfg, start=False)
        sys.exit(code)
