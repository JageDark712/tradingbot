import types

import pytest

from scanner import mt5_bootstrap as boot


def make_config(tmp_path):
    return boot.BootstrapConfig(
        project_dir=tmp_path,
        log_dir=tmp_path / "logs",
        host="127.0.0.1",
        port=18812,
        wine_cmd="wine",
    )


def test_server_down_starts_mt5linux(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    started = []
    ports = iter([False, True])

    monkeypatch.setattr(boot, "is_port_open", lambda host, port, timeout=1.0: next(ports))
    monkeypatch.setattr(boot, "read_pid", lambda path: None)
    monkeypatch.setattr(boot, "start_server_process", lambda config: started.append(config.port) or 4321)
    monkeypatch.setattr(boot, "wait_for_port", lambda host, port, timeout: True)

    result = boot.ensure_server_running(cfg)

    assert result.ok
    assert started == [18812]
    assert "escuchando" in result.message


def test_stale_pid_is_terminated_before_restart(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    killed = []

    monkeypatch.setattr(boot, "is_port_open", lambda host, port, timeout=1.0: False)
    monkeypatch.setattr(boot, "read_pid", lambda path: 123)
    monkeypatch.setattr(boot, "is_pid_running", lambda pid: pid == 123)
    monkeypatch.setattr(boot, "terminate_pid", lambda pid: killed.append(pid))
    monkeypatch.setattr(boot, "start_server_process", lambda config: 456)
    monkeypatch.setattr(boot, "wait_for_port", lambda host, port, timeout: True)

    result = boot.ensure_server_running(cfg)

    assert result.ok
    assert killed == [123]


def test_preflight_fails_when_terminal_disconnected(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)

    monkeypatch.setattr(boot, "check_wine", lambda config: boot.LayerResult("Wine", True, "ok"))
    monkeypatch.setattr(boot, "check_linux_env", lambda config: boot.LayerResult("Linux", True, "ok"))
    monkeypatch.setattr(boot, "check_wine_python", lambda config: boot.LayerResult("Wine Python", True, "ok"))
    monkeypatch.setattr(boot, "ensure_mt5_terminal_running", lambda config: boot.LayerResult("MT5", True, "ok"))
    monkeypatch.setattr(boot, "ensure_server_running", lambda config: boot.LayerResult("mt5linux", True, "ok"))
    monkeypatch.setattr(
        boot,
        "check_mt5_handshake",
        lambda config: boot.LayerResult("MT5 handshake", False, "terminal no conectado al broker"),
    )

    report = boot.run_preflight(cfg)

    assert not report.ok
    assert "broker" in report.results[-1].message


def test_preflight_blocks_non_demo_account(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    mt5 = types.SimpleNamespace(
        initialize=lambda: True,
        terminal_info=lambda: types.SimpleNamespace(connected=True, trade_allowed=True, build=6231),
        account_info=lambda: types.SimpleNamespace(trade_mode=2),
        version=lambda: (500, 6231, "27 Sep 2026"),
        symbol_select=lambda *_: True,
        copy_rates_from_pos=lambda *_: [1],
        last_error=lambda: (1, "ok"),
    )

    monkeypatch.setattr(boot, "create_mt5_client", lambda config: mt5)
    monkeypatch.setattr(boot.settings, "ALLOW_LIVE_ACCOUNT", False, raising=False)

    result = boot.check_mt5_handshake(cfg)

    assert not result.ok
    assert "cuenta real" in result.message.lower()


def test_live_account_allowed_by_setting(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    mt5 = types.SimpleNamespace(
        initialize=lambda: True,
        terminal_info=lambda: types.SimpleNamespace(connected=True, trade_allowed=True, build=6231),
        account_info=lambda: types.SimpleNamespace(trade_mode=2),
        version=lambda: (500, 6231, "27 Sep 2026"),
        symbol_select=lambda *_: True,
        copy_rates_from_pos=lambda *_: [1],
        last_error=lambda: (1, "ok"),
    )

    monkeypatch.setattr(boot, "create_mt5_client", lambda config: mt5)
    monkeypatch.setattr(boot.settings, "ALLOW_LIVE_ACCOUNT", True, raising=False)

    result = boot.check_mt5_handshake(cfg)

    assert result.ok


def test_autotrading_disabled_has_10027_hint(monkeypatch, tmp_path):
    cfg = make_config(tmp_path)
    mt5 = types.SimpleNamespace(
        initialize=lambda: True,
        terminal_info=lambda: types.SimpleNamespace(connected=True, trade_allowed=False, build=6231),
        account_info=lambda: types.SimpleNamespace(trade_mode=0),
        version=lambda: (500, 6231, "27 Sep 2026"),
        symbol_select=lambda *_: True,
        copy_rates_from_pos=lambda *_: [1],
        last_error=lambda: (1, "ok"),
    )

    monkeypatch.setattr(boot, "create_mt5_client", lambda config: mt5)

    result = boot.check_mt5_handshake(cfg)

    assert not result.ok
    assert "10027" in result.message


def test_rpyc_mismatch_is_fatal():
    result = boot.check_expected_versions(
        linux={"rpyc": "5.0.1", "pandas": "2.3.3", "numpy": "2.2.6", "mt5linux": "0.1.9"},
        wine={"rpyc": "6.0.0", "MetaTrader5": "5.0.6231", "python": "Python 3.9.0"},
        terminal_version=(500, 6231, "27 Sep 2026"),
    )

    assert not result.ok
    assert "result expired" in result.message
