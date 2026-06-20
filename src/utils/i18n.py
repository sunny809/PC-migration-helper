"""Translation loader utility for PySide6 i18n support."""

from __future__ import annotations

import os
from typing import Optional

from src.utils.logger import setup_logging

logger = setup_logging()

# Global translator reference to prevent garbage collection
_translator = None


def load_translations(
    app=None,
    language: Optional[str] = None,
    i18n_dir: Optional[str] = None,
) -> bool:
    """Load translation file for the specified language.

    Args:
        app: The QApplication instance (required for installing translator).
        language: Language code (e.g., "zh_CN", "en_US"). If None,
                  uses system locale.
        i18n_dir: Directory containing .qm translation files. If None,
                  uses the default assets/i18n/ directory.

    Returns:
        True if translations were loaded successfully.
    """
    global _translator

    try:
        from PySide6.QtCore import QLocale, QTranslator
    except ImportError:
        logger.warning("PySide6 not available, translations disabled")
        return False

    if app is None:
        logger.warning("No QApplication provided, cannot install translator")
        return False

    # Determine language
    if language is None:
        language = QLocale.system().name()  # e.g., "zh_CN"

    # Determine i18n directory
    if i18n_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        i18n_dir = os.path.join(base_dir, "assets", "i18n")

    # Load .qm file
    translator = QTranslator()
    qm_file = os.path.join(i18n_dir, f"{language}.qm")

    if os.path.exists(qm_file):
        if translator.load(qm_file):
            app.installTranslator(translator)
            _translator = translator  # Prevent GC
            logger.info(f"Loaded translations from {qm_file}")
            return True
        else:
            logger.warning(f"Failed to load translation file: {qm_file}")
    else:
        logger.info(f"Translation file not found: {qm_file}, using default language")

    # For Chinese (zh_CN), we use Chinese as the source text, so no translation needed
    # For other languages, fall back to English if available
    if language != "en_US":
        en_qm = os.path.join(i18n_dir, "en_US.qm")
        if os.path.exists(en_qm):
            if translator.load(en_qm):
                app.installTranslator(translator)
                _translator = translator
                logger.info("Loaded English translations as fallback")
                return True

    return False


def tr(context: str, source_text: str, disambiguation: str = "",
       n: int = -1) -> str:
    """Translate a string using PySide6's translation system.

    This is a convenience function that can be used outside of QObject
    subclasses. Within QObject subclasses, use self.tr() instead.

    Args:
        context: Translation context (usually class name).
        source_text: The source text to translate (Chinese by convention).
        disambiguation: Optional disambiguation string.
        n: Optional plural form number.

    Returns:
        Translated string, or source_text if no translation available.
    """
    try:
        from PySide6.QtCore import QCoreApplication
        if n >= 0:
            return QCoreApplication.translate(context, source_text, disambiguation, n)
        return QCoreApplication.translate(context, source_text, disambiguation)
    except ImportError:
        return source_text
