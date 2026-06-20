"""Tests for human_size utility — file size and duration formatting."""

import pytest

from src.utils.human_size import format_duration, format_size, format_speed


class TestFormatSize:
    """Test format_size function."""

    def test_zero(self):
        assert format_size(0) == "0 B"

    def test_bytes(self):
        assert format_size(500) == "500 B"

    def test_kilobytes_exact(self):
        assert format_size(1024) == "1.00 KB"

    def test_kilobytes_fractional(self):
        result = format_size(1536)
        assert "KB" in result
        assert "1.50" in result

    def test_megabytes(self):
        result = format_size(1024 * 1024)
        assert "MB" in result
        assert "1.00" in result

    def test_gigabytes(self):
        result = format_size(1024 ** 3)
        assert "GB" in result
        assert "1.00" in result

    def test_terabytes(self):
        result = format_size(1024 ** 4)
        assert "TB" in result
        assert "1.00" in result

    def test_negative_returns_zero(self):
        assert format_size(-100) == "0 B"

    def test_large_number(self):
        result = format_size(500 * 1024 ** 3)  # 500 GB
        assert "GB" in result

    def test_exactly_one_byte(self):
        assert format_size(1) == "1 B"


class TestFormatSpeed:
    """Test format_speed function."""

    def test_bytes_per_second(self):
        result = format_speed(500)
        assert "B/s" in result

    def test_megabytes_per_second(self):
        result = format_speed(1024 * 1024)
        assert "MB/s" in result

    def test_zero_speed(self):
        result = format_speed(0)
        assert "0 B/s" in result


class TestFormatDuration:
    """Test format_duration function."""

    def test_seconds_only(self):
        result = format_duration(30)
        assert "30" in result
        assert "秒" in result or "s" in result

    def test_minutes_and_seconds(self):
        result = format_duration(125)  # 2m 5s
        assert "2" in result
        assert "分" in result or "m" in result

    def test_hours_minutes_seconds(self):
        result = format_duration(3665)  # 1h 1m 5s
        assert "时" in result or "h" in result

    def test_negative_returns_zero(self):
        result = format_duration(-10)
        assert "0" in result

    def test_zero(self):
        result = format_duration(0)
        assert "0" in result
