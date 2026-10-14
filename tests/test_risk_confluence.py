import pytest
import os
import tempfile
import pandas as pd
from risk.engine import RiskEngine, OpenPosition
from confluence.scorer import combine_signals, ConfluenceResult
import execution.position_tracker as tracker
import config.settings as settings

# --- RiskEngine Tests ---

def test_risk_engine_limits():
    # Balance $500
    engine = RiskEngine(account_balance=500.0)

    # 1. Test Max Trades Per Category
    limit = settings.MAX_TRADES_PER_CATEGORY
    engine.open_positions = [
        OpenPosition("S", "crypto", "alcista", 1.0, 0.01) for _ in range(limit)
    ]

    # Next trade in 'crypto' should be blocked
    can_open, reason = engine.can_open_trade("crypto", 0.01)
    assert not can_open
    assert f"Límite de {limit} trades simultáneos en 'crypto' alcanzado" in reason

    # 2. Test Max Aggregate Risk
    engine.open_positions = []
    limit_risk = settings.MAX_AGGREGATE_RISK
    # Fill up to almost limit
    engine.open_positions = [
        OpenPosition("S", "crypto", "alcista", 10.0, limit_risk - 0.001),
    ]
    # Adding 0.01 more should block it
    can_open, reason = engine.can_open_trade("forex", 0.01)
    assert not can_open
    assert "superaría el máximo permitido" in reason

def test_risk_engine_calculation():
    engine = RiskEngine(account_balance=1000.0)
    # Use actual base risk from settings
    base_risk = settings.RISK_BASE_BY_CATEGORY["crypto"]
    # Multiplier = 0.5 + 0.5 * strength = 0.5 + 0.5 * 1.0 = 1.0
    risk_pct = engine.calculate_trade_risk_pct("crypto", 1.0)
    assert risk_pct == base_risk * 1.0

# --- Confluence Scorer Tests ---

def test_confluence_regime_weights():
    signals = {
        "trend_following": {"direction": "alcista", "strength": 0.8},
        "momentum": {"direction": "alcista", "strength": 0.8},
    }

    res_trending = combine_signals("EURUSD", signals, regime="TRENDING")
    res_ranging = combine_signals("EURUSD", signals, regime="RANGING")

    assert res_trending.regime == "TRENDING"
    assert res_ranging.regime == "RANGING"
    assert res_trending.agreement == "full"

def test_confluence_partial_signal():
    signals = {
        "trend_following": {"direction": "alcista", "strength": 0.8},
        "momentum": {"direction": "sin_senal", "strength": 0.0},
    }
    res = combine_signals("EURUSD", signals, regime="TRENDING")

    assert res.agreement == "partial"
    # Base score: (0.8 * 0.8) / 0.8 = 0.8
    # Penalty: 0.8 * 0.6 = 0.48
    assert res.confluence_score == 0.48

def test_confluence_conflict():
    signals = {
        "trend_following": {"direction": "alcista", "strength": 0.8},
        "momentum": {"direction": "bajista", "strength": 0.8},
    }
    res = combine_signals("EURUSD", signals, regime="TRENDING")
    assert res.direction == "sin_senal"
    assert res.agreement == "conflict"
    assert res.confluence_score == 0.0

# --- Position Tracker Tests ---

@pytest.fixture
def temp_tracker(tmp_path):
    tracker.TRACKER_FILE = str(tmp_path / "state.json")
    return tracker

def test_tracker_persistence(temp_tracker):
    tracker.register_position(123, "BTCUSDm", "alcista", 80000.0, 500.0)

    state = tracker.get_position_state(123)
    assert state is not None
    assert state["symbol"] == "BTCUSDm"
    assert state["risk_distance"] == 500.0

    tracker.mark_tp_level_hit(123, 0)
    state = tracker.get_position_state(123)
    assert 0 in state["tp_levels_hit"]

    tracker.remove_position(123)
    assert tracker.get_position_state(123) is None
