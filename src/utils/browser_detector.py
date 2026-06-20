"""BrowserDetector — detect installed browsers and locate browser data files.

Supports bookmark detection for:
  - Google Chrome
  - Microsoft Edge
  - Mozilla Firefox
  - Brave
  - Vivaldi
  - Opera

All detected files are returned as FileEntry objects with BROWSER_DATA category,
ready to be added to ScanResult and migrated alongside user documents.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Dict, List, Optional

from src.constants import FileCategory
from src.models.file_entry import FileEntry
from src.utils.logger import setup_logging

logger = setup_logging()


@dataclass
class BrowserInfo:
    """Information about a detected browser installation.

    Attributes:
        name: Display name (e.g. "Google Chrome", "Firefox").
        bookmark_path: Full path to the bookmark file, or None if not found.
        profile_path: Full path to the browser profile directory, or None.
    """
    name: str
    bookmark_path: Optional[str]
    profile_path: Optional[str] = None


class BrowserDetector:
    """Detects installed browsers and locates their bookmark files.

    Usage:
        detector = BrowserDetector()
        browsers = detector.detect_all()
        entries = detector.get_bookmark_entries()
        # -> [FileEntry(..., category=BROWSER_DATA), ...]
    """

    # Chromium-based browsers: bookmark file is %LOCALAPPDATA%\\...\\Bookmarks (JSON)
    _CHROMIUM_BROWSERS: Dict[str, str] = {
        "Google Chrome": r"Google\Chrome\User Data\Default\Bookmarks",
        "Microsoft Edge": r"Microsoft\Edge\User Data\Default\Bookmarks",
        "Brave": r"BraveSoftware\Brave-Browser\User Data\Default\Bookmarks",
        "Vivaldi": r"Vivaldi\User Data\Default\Bookmarks",
        "Opera": r"Opera Software\Opera Stable\Bookmarks",
    }

    # Firefox: bookmark database is %APPDATA%\\Mozilla\\Firefox\\Profiles\\*.default*\\places.sqlite
    _FIREFOX_PROFILES_REL = r"Mozilla\Firefox\Profiles"

    def detect_all(self) -> List[BrowserInfo]:
        """Detect all installed browsers and locate bookmark files.

        Returns:
            List of BrowserInfo, one per detected browser with valid bookmark.
        """
        browsers: List[BrowserInfo] = []
        found = set()  # Avoid duplicates if paths overlap

        # 1. Chromium-based browsers
        for name, rel_path in self._CHROMIUM_BROWSERS.items():
            bookmark_path = self._resolve_chromium_bookmark(rel_path)
            if bookmark_path and bookmark_path not in found:
                found.add(bookmark_path)
                browsers.append(BrowserInfo(
                    name=name,
                    bookmark_path=bookmark_path,
                    profile_path=os.path.dirname(os.path.dirname(bookmark_path)),
                ))
                logger.debug(f"Detected {name} bookmarks at: {bookmark_path}")

        # 2. Firefox — scan profiles for places.sqlite
        firefox_bookmarks = self._find_firefox_bookmarks()
        for bookmark_path in firefox_bookmarks:
            if bookmark_path not in found:
                found.add(bookmark_path)
                profile_dir = os.path.dirname(bookmark_path)
                browsers.append(BrowserInfo(
                    name="Firefox",
                    bookmark_path=bookmark_path,
                    profile_path=profile_dir,
                ))
                logger.debug(f"Detected Firefox bookmarks at: {bookmark_path}")

        if not browsers:
            logger.info("No browser bookmark files found.")
        else:
            names = ", ".join(b.name for b in browsers)
            logger.info(f"Detected {len(browsers)} browsers with bookmarks: {names}")

        return browsers

    def get_bookmark_entries(self) -> List[FileEntry]:
        """Get FileEntry objects for all detected bookmark files.

        Each entry is classified as FileCategory.BROWSER_DATA and pre-selected.

        Returns:
            List of FileEntry objects (one per browser bookmark file).
        """
        browsers = self.detect_all()
        entries: List[FileEntry] = []

        for browser in browsers:
            if not browser.bookmark_path:
                continue
            try:
                size = os.path.getsize(browser.bookmark_path)
                mtime = os.path.getmtime(browser.bookmark_path)
            except OSError:
                logger.warning(f"Cannot stat bookmark file: {browser.bookmark_path}")
                continue

            entry = FileEntry(
                path=browser.bookmark_path,
                size=size,
                modified_time=mtime,
                category=FileCategory.BROWSER_DATA,
                is_selected=True,
            )
            entries.append(entry)

        return entries

    def _resolve_chromium_bookmark(self, rel_path: str) -> Optional[str]:
        """Resolve a Chromium bookmark file path relative to LOCALAPPDATA.

        Args:
            rel_path: Relative path under %LOCALAPPDATA%.

        Returns:
            Absolute path if the file exists, else None.
        """
        local_app_data = os.environ.get("LOCALAPPDATA", "")
        if not local_app_data:
            return None
        full_path = os.path.join(local_app_data, rel_path.replace("\\", os.sep))
        if os.path.isfile(full_path):
            return full_path
        return None

    def _find_firefox_bookmarks(self) -> List[str]:
        """Find Firefox places.sqlite files in all profiles.

        Returns:
            List of paths to places.sqlite files found.
        """
        app_data = os.environ.get("APPDATA", "")
        if not app_data:
            return []
        profiles_dir = os.path.join(app_data, self._FIREFOX_PROFILES_REL.replace("\\", os.sep))
        if not os.path.isdir(profiles_dir):
            return []

        results: List[str] = []
        try:
            for entry in os.scandir(profiles_dir):
                if not entry.is_dir(follow_symlinks=False):
                    continue
                places_path = os.path.join(entry.path, "places.sqlite")
                if os.path.isfile(places_path):
                    results.append(places_path)
        except (PermissionError, OSError) as e:
            logger.warning(f"Cannot scan Firefox profiles at {profiles_dir}: {e}")

        return results
