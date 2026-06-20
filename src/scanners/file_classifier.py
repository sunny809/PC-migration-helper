"""FileClassifier — classifies files by category based on configurable rules."""

from __future__ import annotations

import os
from pathlib import PureWindowsPath
from typing import Dict, FrozenSet, List, Optional, Set

import yaml

from src.constants import FileCategory
from src.utils.logger import setup_logging

logger = setup_logging()


class FileClassifier:
    """Classifies files into categories using a priority-ordered rule chain.

    Rule chain (highest to lowest priority):
    1. Path-based rules: If the path contains a known directory pattern,
       assign the corresponding category.
    2. Extension-based rules: Map file extension to category.
    3. Fallback: FileCategory.OTHER

    Also determines whether a path should be excluded from scanning
    (system directories, application directories, etc.).

    All rules are loaded from a YAML configuration file.
    """

    def __init__(self, config_path: Optional[str] = None):
        """Initialize the classifier with rules from a config file.

        Args:
            config_path: Path to the YAML rules file. If None, uses
                         the default config/default_rules.yaml.
        """
        if config_path is None:
            # Default config relative to this file's project root
            base_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            config_path = os.path.join(base_dir, "config", "default_rules.yaml")

        self._config_path = config_path
        self._config = self._load_config(config_path)

        # Build extension -> category mapping
        self._ext_map: Dict[str, FileCategory] = {}
        classification = self._config.get("classification", {})
        for category_name, extensions in classification.items():
            try:
                category = FileCategory(category_name)
            except ValueError:
                logger.warning(f"Unknown category in config: {category_name}")
                continue
            for ext in extensions:
                normalized = ext.lower()
                if not normalized.startswith("."):
                    normalized = f".{normalized}"
                self._ext_map[normalized] = category

        # Build path hint -> category mapping
        self._path_hints: Dict[str, FileCategory] = {}
        path_hints = self._config.get("path_hints", {})
        for category_name, dir_names in path_hints.items():
            try:
                category = FileCategory(category_name)
            except ValueError:
                continue
            for dir_name in dir_names:
                self._path_hints[dir_name.lower()] = category

        # Build exclusion sets
        scan_config = self._config.get("scan", {})
        self._exclude_paths: Set[str] = set(
            p.lower().rstrip("\\") for p in scan_config.get("exclude_paths", [])
        )
        self._exclude_patterns: List[str] = scan_config.get("exclude_patterns", [])
        self._exclude_extensions: FrozenSet[str] = frozenset(
            ext.lower() if isinstance(ext, str) and ext.startswith(".") else f".{str(ext).lower()}"
            for ext in scan_config.get("exclude_extensions", [])
            if isinstance(ext, str)
        )
        self._max_file_size: int = scan_config.get("max_file_size", 4 * 1024 ** 3)
        self._min_file_size: int = scan_config.get("min_file_size", 0)
        self._skip_system: bool = "system" in scan_config.get("skip_attributes", [])
        self._skip_hidden: bool = "hidden" in scan_config.get("skip_attributes", [])

        logger.info(
            f"FileClassifier loaded: {len(self._ext_map)} extensions, "
            f"{len(self._path_hints)} path hints, "
            f"{len(self._exclude_paths)} excluded paths"
        )

    @staticmethod
    def _load_config(config_path: str) -> dict:
        """Load and parse the YAML configuration file."""
        try:
            with open(config_path, "r", encoding="utf-8") as f:
                return yaml.safe_load(f) or {}
        except FileNotFoundError:
            logger.warning(f"Config file not found: {config_path}, using empty config")
            return {}
        except yaml.YAMLError as e:
            logger.error(f"Failed to parse config YAML: {e}")
            return {}

    def classify(self, path: str, ext: Optional[str] = None) -> FileCategory:
        """Classify a file into a category.

        Args:
            path: Full file path.
            ext: Pre-computed lowercase extension (optimization). If None,
                 it will be computed from the path.

        Returns:
            The determined FileCategory.
        """
        # Priority 1: Path-based hints
        path_lower = path.lower()
        # Check each path component against hints
        # Use PureWindowsPath for proper Windows path parsing
        try:
            parts = PureWindowsPath(path).parts
        except Exception:
            parts = path.replace("\\", "/").split("/")

        for part in parts:
            part_lower = part.lower()
            if part_lower in self._path_hints:
                return self._path_hints[part_lower]

        # Priority 2: Extension-based rules
        if ext is None:
            _, ext = os.path.splitext(path)
            ext = ext.lower()

        if ext and ext in self._ext_map:
            return self._ext_map[ext]

        # Priority 3: Fallback
        return FileCategory.OTHER

    def is_excluded_path(self, path: str) -> bool:
        """Check if a directory path should be excluded from scanning.

        Args:
            path: Directory path to check.

        Returns:
            True if the path should be skipped.
        """
        path_lower = path.lower().rstrip("\\")

        # Check exact exclude paths
        if path_lower in self._exclude_paths:
            return True

        # Check if path starts with any excluded path
        for excluded in self._exclude_paths:
            if path_lower.startswith(excluded + "\\"):
                return True

        # Check user-profile-relative patterns
        # (e.g., AppData/Local/Temp/** relative to C:\Users\<username>)
        user_profile = os.environ.get("USERPROFILE", "").lower()
        if user_profile and path_lower.startswith(user_profile):
            relative = path_lower[len(user_profile):].lstrip("\\").replace("\\", "/")
            for pattern in self._exclude_patterns:
                # Simple glob matching: strip /** and check prefix
                pattern_base = pattern.rstrip("*").rstrip("/")
                if relative.startswith(pattern_base):
                    return True

        return False

    def is_excluded_extension(self, ext: str) -> bool:
        """Check if a file extension should be excluded.

        Args:
            ext: File extension in lowercase (including the dot).

        Returns:
            True if files with this extension should be skipped.
        """
        normalized = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        return normalized in self._exclude_extensions

    def should_skip_file(self, path: str, size: int, is_hidden: bool = False,
                         is_system: bool = False) -> bool:
        """Determine if a file should be skipped during scanning.

        Args:
            path: File path.
            size: File size in bytes.
            is_hidden: Whether the file has the hidden attribute.
            is_system: Whether the file has the system attribute.

        Returns:
            True if the file should be skipped.
        """
        # Check extension
        _, ext = os.path.splitext(path)
        if self.is_excluded_extension(ext):
            return True

        # Check file size limits
        if size > self._max_file_size or size < self._min_file_size:
            return True

        # Check attributes
        if self._skip_hidden and is_hidden:
            return True
        if self._skip_system and is_system:
            return True

        return False

    @property
    def skip_hidden(self) -> bool:
        """Whether to skip hidden files/directories."""
        return self._skip_hidden

    @property
    def skip_system(self) -> bool:
        """Whether to skip system files/directories."""
        return self._skip_system
