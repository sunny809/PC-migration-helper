"""Tests for FileClassifier."""

import os
import tempfile

import pytest

from src.constants import FileCategory
from src.scanners.file_classifier import FileClassifier


@pytest.fixture
def classifier():
    """Create a FileClassifier with default config."""
    # Project root is 2 levels up from this test file (tests/ -> migrate/)
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    config_path = os.path.join(project_root, "config", "default_rules.yaml")
    return FileClassifier(config_path)


class TestFileClassifier:
    """Test file classification logic."""

    def test_classify_document_by_extension(self, classifier):
        """Test that document extensions are classified correctly."""
        assert classifier.classify("C:\\Users\\test\\report.docx") == FileCategory.DOCUMENTS
        assert classifier.classify("C:\\Users\\test\\data.xlsx") == FileCategory.DOCUMENTS
        assert classifier.classify("C:\\Users\\test\\readme.pdf") == FileCategory.DOCUMENTS
        assert classifier.classify("C:\\Users\\test\\notes.txt") == FileCategory.DOCUMENTS

    def test_classify_photo_by_extension(self, classifier):
        """Test that photo extensions are classified correctly."""
        assert classifier.classify("C:\\Users\\test\\photo.jpg") == FileCategory.PHOTOS
        assert classifier.classify("C:\\Users\\test\\image.png") == FileCategory.PHOTOS
        assert classifier.classify("C:\\Users\\test\\pic.heic") == FileCategory.PHOTOS

    def test_classify_video_by_extension(self, classifier):
        """Test that video extensions are classified correctly."""
        assert classifier.classify("D:\\movie.mp4") == FileCategory.VIDEOS
        assert classifier.classify("D:\\clip.mkv") == FileCategory.VIDEOS

    def test_classify_music_by_extension(self, classifier):
        """Test that music extensions are classified correctly."""
        assert classifier.classify("C:\\song.mp3") == FileCategory.MUSIC
        assert classifier.classify("C:\\album.flac") == FileCategory.MUSIC

    def test_classify_archive_by_extension(self, classifier):
        """Test that archive extensions are classified correctly."""
        assert classifier.classify("C:\\backup.zip") == FileCategory.ARCHIVES
        assert classifier.classify("C:\\data.7z") == FileCategory.ARCHIVES

    def test_classify_unknown_extension(self, classifier):
        """Test that unknown extensions fall back to OTHER."""
        assert classifier.classify("C:\\data.xyz") == FileCategory.OTHER
        assert classifier.classify("C:\\config.json") == FileCategory.OTHER

    def test_classify_by_path_hint(self, classifier):
        """Test that path-based hints override extension classification."""
        # A .dat file in Documents should be classified as DOCUMENTS
        # (path hint takes priority)
        assert classifier.classify("C:\\Users\\test\\Documents\\data.dat") == FileCategory.DOCUMENTS
        assert classifier.classify("C:\\Users\\test\\Pictures\\data.dat") == FileCategory.PHOTOS
        assert classifier.classify("C:\\Users\\test\\Music\\data.dat") == FileCategory.MUSIC

    def test_precomputed_extension(self, classifier):
        """Test that pre-computed extension is used when provided."""
        assert classifier.classify("report.docx", ext=".docx") == FileCategory.DOCUMENTS

    def test_excluded_path_windows(self, classifier):
        """Test that Windows system paths are excluded."""
        assert classifier.is_excluded_path("C:\\Windows")
        assert classifier.is_excluded_path("C:\\Windows\\System32")
        assert classifier.is_excluded_path("C:\\Program Files")
        assert classifier.is_excluded_path("C:\\Program Files (x86)\\App")
        assert classifier.is_excluded_path("C:\\ProgramData")
        assert classifier.is_excluded_path("C:\\$Recycle.Bin")

    def test_non_excluded_path(self, classifier):
        """Test that user paths are not excluded."""
        assert not classifier.is_excluded_path("C:\\Users\\test\\Documents")
        assert not classifier.is_excluded_path("D:\\MyFiles")
        assert not classifier.is_excluded_path("E:\\")

    def test_excluded_extension(self, classifier):
        """Test that system file extensions are excluded."""
        assert classifier.is_excluded_extension(".sys")
        assert classifier.is_excluded_extension(".dll")
        assert classifier.is_excluded_extension(".exe")
        assert classifier.is_excluded_extension(".ini")
        assert classifier.is_excluded_extension(".tmp")

    def test_non_excluded_extension(self, classifier):
        """Test that document extensions are not excluded."""
        assert not classifier.is_excluded_extension(".docx")
        assert not classifier.is_excluded_extension(".pdf")
        assert not classifier.is_excluded_extension(".jpg")

    def test_should_skip_file_by_extension(self, classifier):
        """Test file skipping by extension."""
        assert classifier.should_skip_file("C:\\app.exe", 1000)
        assert classifier.should_skip_file("C:\\driver.sys", 1000)

    def test_should_skip_file_by_size(self, classifier):
        """Test file skipping by size limits."""
        # File too large (> 4GB)
        assert classifier.should_skip_file("C:\\big.docx", 5 * 1024**3)
        # Normal file should not be skipped
        assert not classifier.should_skip_file("C:\\normal.docx", 1024)

    def test_should_skip_file_by_attributes(self, classifier):
        """Test file skipping by hidden/system attributes."""
        assert classifier.should_skip_file("C:\\hidden.docx", 1000, is_hidden=True)
        assert classifier.should_skip_file("C:\\system.dat", 1000, is_system=True)

    def test_normal_file_not_skipped(self, classifier):
        """Test that normal files are not skipped."""
        assert not classifier.should_skip_file("C:\\report.docx", 50000)
        assert not classifier.should_skip_file("D:\\photo.jpg", 2000000)
