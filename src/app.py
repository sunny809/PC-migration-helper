"""Application initialization — sets up QApplication, translations, and theme."""

from __future__ import annotations

import os
import sys
from typing import Optional

from src.constants import APP_NAME, APP_NAME_ZH, ORGANIZATION
from src.utils.logger import setup_logging

logger = setup_logging()


def create_app(argv: Optional[list] = None) -> object:
    """Create and configure the QApplication instance.

    Args:
        argv: Command-line arguments. If None, uses sys.argv.

    Returns:
        The configured QApplication instance.
    """
    try:
        from PySide6.QtWidgets import QApplication
    except ImportError:
        logger.error("PySide6 is not installed. Please install it with: pip install PySide6")
        sys.exit(1)

    if argv is None:
        argv = sys.argv

    app = QApplication(argv)
    app.setApplicationName(APP_NAME)
    app.setOrganizationName(ORGANIZATION)

    # Load theme stylesheet
    _load_stylesheet(app)

    # Load translations
    from src.utils.i18n import load_translations
    load_translations(app)

    # Global exception handler
    def exception_hook(exc_type, exc_value, exc_tb):
        """Handle uncaught exceptions in the main thread."""
        logger.error(
            f"Uncaught exception: {exc_type.__name__}: {exc_value}",
            exc_info=(exc_type, exc_value, exc_tb),
        )

        # Show error dialog if Qt is available
        try:
            from PySide6.QtWidgets import QMessageBox
            msg = QMessageBox()
            msg.setIcon(QMessageBox.Icon.Critical)
            msg.setWindowTitle("错误 / Error")
            msg.setText(f"发生未预期的错误 / An unexpected error occurred:\n{exc_value}")
            msg.setDetailedText("".join(
                import_traceback().format_exception(exc_type, exc_value, exc_tb)
            ))
            msg.exec()
        except Exception:
            pass

    sys.excepthook = exception_hook

    return app


def _load_stylesheet(app) -> None:
    """Load the application stylesheet from theme.qss."""
    try:
        # Find theme.qss relative to this file
        this_dir = os.path.dirname(os.path.abspath(__file__))
        qss_path = os.path.join(this_dir, "ui", "styles", "theme.qss")

        if os.path.exists(qss_path):
            with open(qss_path, "r", encoding="utf-8") as f:
                app.setStyleSheet(f.read())
            logger.info(f"Loaded stylesheet from {qss_path}")
        else:
            logger.warning(f"Stylesheet not found: {qss_path}")
    except Exception as e:
        logger.error(f"Failed to load stylesheet: {e}")


def import_traceback():
    """Import traceback module lazily."""
    import traceback
    return traceback


def run_app(app=None) -> int:
    """Run the application event loop.

    Args:
        app: QApplication instance. If None, creates one.

    Returns:
        Exit code from the application.
    """
    if app is None:
        app = create_app()

    from src.ui.main_window import MainWindow
    window = MainWindow()
    window.show()

    return app.exec()
