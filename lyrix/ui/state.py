"""Persistent UI state, written to ~/.lyrix/settings-qt.json."""

from __future__ import annotations

import contextlib
import json
import logging
import os
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
        with tmp.open("w", encoding="utf-8") as fh:
            fh.write(json.dumps(state, indent=2))
            fh.flush()
            os.fsync(fh.fileno())
        tmp.replace(STATE_PATH)
    except (OSError, TypeError) as exc:
        _log.error("Failed to write UI state: %s", exc)
        with contextlib.suppress(OSError):
            tmp.unlink(missing_ok=True)


class WindowState(QObject):
    """Window geometry and sash position."""

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
