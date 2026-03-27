from __future__ import annotations

import sys
from pathlib import Path

# ---------------------------------------------------------------------------
# Bootstrap: make src/ importable without install
# ---------------------------------------------------------------------------
_src_dir = Path(__file__).parent
if str(_src_dir) not in sys.path:
    sys.path.insert(0, str(_src_dir))

from PyQt6.QtGui import QIcon
from PyQt6.QtWidgets import QApplication, QMessageBox  # noqa: E402

from utils.logger import get_app_data_dir, setup_logger  # noqa: E402
from utils.config import ConfigManager  # noqa: E402
from utils.startup import StartupChecker  # noqa: E402


def _load_app_icon() -> QIcon:
    """Load the TexPaste application icon."""
    icon_path = Path(__file__).parent / "resources" / "icons" / "texpaste.ico"
    if icon_path.exists():
        return QIcon(str(icon_path))
    return QIcon()


def _show_fatal_error(title: str, message: str) -> None:
    """Display a modal error dialog, then exit."""
    app = QApplication.instance() or QApplication(sys.argv)
    QMessageBox.critical(None, title, message)  # type: ignore[arg-type]
    sys.exit(1)


def main() -> None:
    # ------------------------------------------------------------------
    # 1. Create QApplication first (required for any Qt usage)
    # ------------------------------------------------------------------
    app = QApplication(sys.argv)
    app.setApplicationName("TexPaste")
    app.setApplicationVersion("1.0.0")
    app.setOrganizationName("TexPaste")
    app.setWindowIcon(_load_app_icon())
    # Tray-only app — don't quit when all windows are closed
    app.setQuitOnLastWindowClosed(False)

    # ------------------------------------------------------------------
    # 2. Determine paths
    # ------------------------------------------------------------------
    app_data_dir = get_app_data_dir()
    config_path = app_data_dir / "config.json"

    # ------------------------------------------------------------------
    # 3. Setup logging
    # ------------------------------------------------------------------
    logger = setup_logger(app_data_dir / "logs")
    logger.info("TexPaste starting up — app_data_dir=%s", app_data_dir)

    # ------------------------------------------------------------------
    # 4. Startup checks
    # ------------------------------------------------------------------
    pandoc_exe = "pandoc"
    checker = StartupChecker(config_path=config_path, pandoc_executable=pandoc_exe)
    errors = checker.check_all()

    fatal_errors = [e for e in errors if e.fatal]
    warnings = [e for e in errors if not e.fatal]

    if fatal_errors:
        _show_fatal_error(
            "TexPaste 启动失败",
            "\n\n".join(e.message for e in fatal_errors),
        )
        return  # unreachable but satisfies linters

    # ------------------------------------------------------------------
    # 5. Load configuration
    # ------------------------------------------------------------------
    config = ConfigManager(config_path)

    # ------------------------------------------------------------------
    # 6. Start application controller
    # ------------------------------------------------------------------
    from app.controller import AppController  # noqa: E402 (after Qt init)

    controller = AppController(config)

    # Show non-fatal warnings via tray after event loop starts
    if warnings:
        from PyQt6.QtCore import QTimer
        for warning in warnings:
            from PyQt6.QtWidgets import QSystemTrayIcon
            QTimer.singleShot(
                1000,
                lambda msg=warning.message: controller.tray.show_notification(
                    "TexPaste",
                    msg,
                    QSystemTrayIcon.MessageIcon.Warning,
                ),
            )

    logger.info("Event loop starting")
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
