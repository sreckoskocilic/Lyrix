"""Palette, fonts and metrics for the QML UI.

Values match mockups/06b-dense-large.html: lyr=16 ui=15 lh=1.30 row=1
win=1020 side=360 sec=#c98a4b.
"""

from __future__ import annotations

import sys
from pathlib import Path
from typing import Final


def package_dir() -> Path:
    """Where qml/ and fonts/ live: beside this file, or under PyInstaller's unpack dir."""
    bundled = getattr(sys, "_MEIPASS", "")
    return Path(bundled) / "lyrix" / "ui" if bundled else Path(__file__).parent


FONT_DIR: Final[Path] = package_dir() / "fonts"
FONT_FILES: Final[tuple[Path, ...]] = (
    FONT_DIR / "Roboto Mono for Powerline.ttf",
    FONT_DIR / "Roboto Mono Bold for Powerline.ttf",
)
FONT_FAMILY: Final[str] = "Roboto Mono for Powerline"

PALETTE: Final[dict[str, str]] = {
    "ground": "#1c1c1c",
    "panel": "#232323",
    "sunk": "#161616",
    "line": "#2e2e2e",
    "line_strong": "#3d3d3d",
    "text": "#8fb96f",
    "dim": "#8a9a76",
    "faint": "#6d7a5e",
    "artist": "#c4c85a",
    "album": "#c98a4b",
    "song": "#6fa8bd",
    "accent": "#4ec9c9",
    "select": "#3a3a24",
    "section": "#c98a4b",
}

METRICS: Final[dict[str, float]] = {
    "ui": 15,
    "lyrics": 16,
    "lineHeight": 1.30,
    "rowPad": 1,
    "rowHeight": 23,
    "sidebar": 360,
    "windowWidth": 1020,
    "windowHeight": 680,
    "minWidth": 900,
    "minHeight": 540,
}

LYRICS_SIZE_MIN: Final[int] = 6
LYRICS_SIZE_MAX: Final[int] = 32
LYRICS_SIZE_DEFAULT: Final[int] = 16
