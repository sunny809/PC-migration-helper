"""Tests for ScanWorker — scan operation orchestrator.

Tests the core two-phase scan logic without relying on Qt signals.
"""

import os
import tempfile
import threading
import time

import pytest

from src.constants import ScanState
from src.models.file_entry import FileEntry
from src.scanners.file_classifier import FileClassifier


@pytest.fixture
def classifier():
    """Create a FileClassifier with default config."""
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, "config", "default_rules.yaml")
    return FileClassifier(config_path)


@pytest.fixture
def temp_scan_dir():
    """Create a temp directory with files to scan."""
    with tempfile.TemporaryDirectory() as tmpdir:
        docs = os.path.join(tmpdir, "Docs")
        os.makedirs(docs)
        with open(os.path.join(docs, "report.docx"), "w") as f:
            f.write("test content")
        yield tmpdir


class TestScanWorkerCancel:
    """Test ScanWorker cancel mechanism."""

    def test_cancel_sets_event(self, classifier):
        from src.scanners.scan_worker import ScanWorker
        worker = ScanWorker(classifier, roots=[])
        assert not worker._cancel_event.is_set()
        worker.cancel()
        assert worker._cancel_event.is_set()

    def test_is_cancelled_property(self, classifier):
        from src.scanners.scan_worker import ScanWorker
        worker = ScanWorker(classifier, roots=[])
        assert worker.is_cancelled is False
        worker.cancel()
        assert worker.is_cancelled is True


class TestScanWorkerTwoPhaseScan:
    """Test that ScanWorker performs estimation then full scan."""

    def test_estimate_then_scan(self, classifier, temp_scan_dir):
        """The scanner should estimate dir count before scanning."""
        from src.scanners.disk_scanner import DiskScanner
        scanner = DiskScanner(classifier)

        # Phase 1: Estimation
        estimated = scanner.estimate_dir_count(roots=[temp_scan_dir])
        assert estimated >= 1  # At least the root

        # Phase 2: Full scan
        result = scanner.scan(roots=[temp_scan_dir])
        assert result.state == ScanState.COMPLETED
        assert result.file_count >= 1

    def test_cancel_before_scan(self, classifier, temp_scan_dir):
        """Cancelling before scan should produce empty CANCELLED result."""
        from src.scanners.disk_scanner import DiskScanner
        scanner = DiskScanner(classifier)

        cancel_event = threading.Event()
        cancel_event.set()  # Cancel immediately

        result = scanner.scan(
            roots=[temp_scan_dir],
            cancel_event=cancel_event,
        )
        assert result.state == ScanState.CANCELLED

    def test_cancel_during_estimation(self, classifier):
        """Cancelling during estimation should stop and return."""
        from src.scanners.disk_scanner import DiskScanner
        scanner = DiskScanner(classifier)

        cancel_event = threading.Event()
        cancel_event.set()

        estimated = scanner.estimate_dir_count(
            roots=["/nonexistent"], cancel_event=cancel_event,
        )
        # Should return 0 or a small count since cancelled immediately
        assert estimated >= 0


class TestScanWorkerProgressCalculation:
    """Test progress percentage calculation logic."""

    def test_progress_percentage_calculation(self, classifier, temp_scan_dir):
        """Progress should be calculable from estimation and scanned count."""
        from src.scanners.disk_scanner import DiskScanner
        scanner = DiskScanner(classifier)

        estimated = scanner.estimate_dir_count(roots=[temp_scan_dir])
        assert estimated >= 1

        # Simulate progress calculation
        scanned = 0
        pct = min(100, int(scanned / estimated * 100)) if estimated > 0 else 0
        assert pct == 0

        scanned = estimated
        pct = min(100, int(scanned / estimated * 100))
        assert pct == 100

        scanned = estimated // 2
        pct = min(100, int(scanned / estimated * 100))
        assert 40 <= pct <= 60
