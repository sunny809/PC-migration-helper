"""pytest configuration — sets up QApplication for Qt widget tests when PySide6 is available."""

import pytest

try:
    from PySide6.QtWidgets import QApplication
    HAS_PYSIDE6 = True
except ImportError:
    HAS_PYSIDE6 = False


@pytest.fixture(scope="session", autouse=True)
def qapp():
    """Auto-create QApplication for all tests when PySide6 is available.

    Qt requires a QApplication instance before any QWidget can be created.
    This fixture ensures it exists for the entire test session.
    On dev machines without PySide6, the stubs are used instead.
    """
    if not HAS_PYSIDE6:
        return None
    app = QApplication.instance()
    if app is None:
        app = QApplication([])
    return app
