"""Entry point for the QML Lyrics Browser."""

from __future__ import annotations

import logging
import logging.handlers
import sys
from pathlib import Path

from PySide6.QtCore import QUrl
from PySide6.QtGui import QFont, QFontDatabase, QGuiApplication
from PySide6.QtQml import QQmlApplicationEngine

from ..catalog import _BASE_DIR, get_resource_path
from .controller import Controller
from .models import CatalogModel
from .state import WindowState
from .theme import FONT_FAMILY, FONT_FILES, METRICS, PALETTE, package_dir

QML_DIR: Path = package_dir() / "qml"
LOG_PATH = _BASE_DIR / "lyrix.log"


def _setup_logging() -> None:
    """Log warnings and errors to ~/.lyrix/lyrix.log (256 KB, one backup)."""
    if logging.root.handlers:
        return
    _BASE_DIR.mkdir(parents=True, exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.handlers.RotatingFileHandler(
                LOG_PATH, maxBytes=256 * 1024, backupCount=1, encoding="utf-8"
            )
        ],
    )


def _load_fonts() -> str:
    families: list[str] = []
    for path in FONT_FILES:
        font_id = QFontDatabase.addApplicationFont(str(path))
        if font_id != -1:
            families.extend(QFontDatabase.applicationFontFamilies(font_id))
    return families[0] if families else FONT_FAMILY


def main() -> int:
    import dotenv

    dotenv.load_dotenv(get_resource_path(".env"), override=True)
    _setup_logging()

    app = QGuiApplication(sys.argv)
    app.setApplicationName("Lyrix")
    app.setOrganizationName("Lyrix")
    family = _load_fonts()
    app.setFont(QFont(family, int(METRICS["ui"])))

    model = CatalogModel()
    controller = Controller(model)
    window_state = WindowState()
    app.aboutToQuit.connect(controller.shutdown)

    engine = QQmlApplicationEngine()
    ctx = engine.rootContext()
    ctx.setContextProperty("Theme", dict(PALETTE))
    ctx.setContextProperty("Metrics", dict(METRICS))
    ctx.setContextProperty("FontFamily", family)
    ctx.setContextProperty("CatalogRows", model)
    ctx.setContextProperty("Controller", controller)
    ctx.setContextProperty("WindowState", window_state)
    engine.load(QUrl.fromLocalFile(str(QML_DIR / "Main.qml")))
    if not engine.rootObjects():
        return 1
    return app.exec()


if __name__ == "__main__":
    sys.exit(main())
