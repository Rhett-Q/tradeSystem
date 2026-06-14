from __future__ import annotations

from minqmt.qmt_bootstrap import configure_qmt

from web.state import AppState

_state: AppState | None = None


def get_state() -> AppState:
    global _state
    if _state is None:
        configure_qmt()
        _state = AppState()
        _state.load()
    return _state
