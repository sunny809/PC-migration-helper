"""Tests for DriveDetector — drive detection and filtering."""

from unittest.mock import MagicMock, patch

import pytest

from src.models.migration_target import DriveType, MigrationTarget


def _make_target(letter, label="", drive_type=DriveType.LOCAL,
                total=10**9, free=5*10**8):
    """Helper to create a MigrationTarget."""
    return MigrationTarget(
        drive_letter=letter, label=label, drive_type=drive_type,
        total_bytes=total, free_bytes=free,
    )


class TestDriveDetector:
    """Test DriveDetector filtering logic."""

    @patch("src.targets.drive_detector.DriveDetector.detect_all")
    def test_detect_migration_targets_excludes_c_drive(self, mock_detect_all):
        """C: drive should be excluded from migration targets."""
        from src.targets.drive_detector import DriveDetector
        mock_detect_all.return_value = [
            _make_target("C:", "System", DriveType.LOCAL),
            _make_target("D:", "Data", DriveType.LOCAL),
            _make_target("E:", "USB", DriveType.REMOVABLE),
        ]
        detector = DriveDetector()
        targets = detector.detect_migration_targets()
        letters = [t.drive_letter for t in targets]
        assert "C:" not in letters
        assert "D:" in letters
        assert "E:" in letters

    @patch("src.targets.drive_detector.DriveDetector.detect_all")
    def test_detect_migration_targets_excludes_cdrom(self, mock_detect_all):
        """CD-ROM drives should be excluded from migration targets."""
        from src.targets.drive_detector import DriveDetector
        mock_detect_all.return_value = [
            _make_target("D:", "Data", DriveType.LOCAL),
            _make_target("F:", "CD", DriveType.CDROM),
            _make_target("E:", "USB", DriveType.REMOVABLE),
        ]
        detector = DriveDetector()
        targets = detector.detect_migration_targets()
        types = [t.drive_type for t in targets]
        assert DriveType.CDROM not in types
        assert DriveType.REMOVABLE in types

    @patch("src.targets.drive_detector.DriveDetector.detect_all")
    def test_detect_removable_only_removable_and_network(self, mock_detect_all):
        """detect_removable should only return removable and network drives."""
        from src.targets.drive_detector import DriveDetector
        mock_detect_all.return_value = [
            _make_target("C:", "System", DriveType.LOCAL),
            _make_target("E:", "USB", DriveType.REMOVABLE),
            _make_target("Z:", "NAS", DriveType.NETWORK),
        ]
        detector = DriveDetector()
        targets = detector.detect_removable()
        types = [t.drive_type for t in targets]
        assert DriveType.LOCAL not in types
        assert DriveType.REMOVABLE in types
        assert DriveType.NETWORK in types

    @patch("src.targets.drive_detector.DriveDetector.detect_all")
    def test_detect_migration_targets_empty(self, mock_detect_all):
        """No drives should return empty list."""
        from src.targets.drive_detector import DriveDetector
        mock_detect_all.return_value = []
        detector = DriveDetector()
        targets = detector.detect_migration_targets()
        assert targets == []

    @patch("src.targets.drive_detector.DriveDetector.detect_all")
    def test_detect_migration_targets_includes_non_system_local(self, mock_detect_all):
        """Non-C: local drives should be included as migration targets."""
        from src.targets.drive_detector import DriveDetector
        mock_detect_all.return_value = [
            _make_target("C:", "System", DriveType.LOCAL),
            _make_target("D:", "Data", DriveType.LOCAL),
        ]
        detector = DriveDetector()
        targets = detector.detect_migration_targets()
        letters = [t.drive_letter for t in targets]
        assert "D:" in letters
        assert "C:" not in letters
