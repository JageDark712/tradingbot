"""
Registro local (JSON) de posiciones abiertas por el scanner, para poder
rastrear su distancia de riesgo original y qué niveles de TP ya se
activaron (MT5 no guarda esta información una vez que el SL se mueve).
"""
import json
import os

TRACKER_FILE = "execution/open_positions_state.json"


def _load_state() -> dict:
    if not os.path.exists(TRACKER_FILE):
        return {}
    with open(TRACKER_FILE, "r") as f:
        return json.load(f)


def _save_state(state: dict):
    with open(TRACKER_FILE, "w") as f:
        json.dump(state, f, indent=2)


def register_position(ticket: int, symbol: str, direction: str, entry_price: float, risk_distance: float):
    """Registra una nueva posición al abrirla, guardando su riesgo original."""
    state = _load_state()
    state[str(ticket)] = {
        "symbol": symbol,
        "direction": direction,
        "entry_price": entry_price,
        "risk_distance": risk_distance,
        "tp_levels_hit": [],  # índices de niveles ya ejecutados, ej. [0, 1]
    }
    _save_state(state)


def get_position_state(ticket: int) -> dict:
    state = _load_state()
    return state.get(str(ticket))


def mark_tp_level_hit(ticket: int, level_index: int):
    state = _load_state()
    if str(ticket) in state:
        if level_index not in state[str(ticket)]["tp_levels_hit"]:
            state[str(ticket)]["tp_levels_hit"].append(level_index)
        _save_state(state)


def remove_position(ticket: int):
    """Elimina el registro cuando una posición se cierra por completo."""
    state = _load_state()
    state.pop(str(ticket), None)
    _save_state(state)


def get_all_tracked_tickets() -> list:
    return list(_load_state().keys())
