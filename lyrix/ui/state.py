"""Persistent UI state for the QML app.

Written to ~/.lyrix/settings-qt.json so the Tkinter app's settings.json stays
untouched while both apps exist.
"""

from __future__ import annotations

import contextlib
import json
import logging
from typing import cast

from PySide6.QtCore import QObject, Slot

from ..catalog import _BASE_DIR

STATE_PATH = _BASE_DIR / "settings-qt.json"
_log = logging.getLogger(__name__)


def read_state() -> dict[str, object]:
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return cast("dict[str, object]", data) if isinstance(data, dict) else {}


def write_state(patch: dict[str, object]) -> None:
    state = read_state()
    state.update(patch)
    tmp = STATE_PATH.with_suffix(".tmp")
    try:
        STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
        tmp.write_text(json.dumps(state, indent=2), encoding="utf-8")
        tmp.replace(STATE_PATH)
    except (OSError, TypeError) as exc:
        _log.error("Failed to write UI state: %s", exc)
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)


class WindowState(QObject):
    """Window geometry, sash position and lyrics font size."""

    @Slot(result="QVariantMap")
    def geometry(self) -> dict[str, object]:
        geom = read_state().get("geometry")
        if not isinstance(geom, dict):
            return {}
        return {k: v for k, v in geom.items() if isinstance(v, int)}

    @Slot(int, int, int, int)
    def save_geometry(self, width: int, height: int, x: int, y: int) -> None:
        write_state({"geometry": {"width": width, "height": height, "x": x, "y": y}})

    @Slot(result=float)
    def sash(self) -> float:
        value = read_state().get("sash")
        return float(value) if isinstance(value, (int, float)) else 0.0

    @Slot(float)
    def save_sash(self, position: float) -> None:
        write_state({"sash": position})

    @Slot(result=int)
    def lyrics_size(self) -> int:
        value = read_state().get("lyrics_size")
        return value if isinstance(value, int) else 0

    @Slot(int)
    def save_lyrics_size(self, size: int) -> None:
        write_state({"lyrics_size": size})
