"""Human-readable file size formatting."""


def format_size(size_bytes: int | float) -> str:
    """Convert byte count to human-readable string.

    Args:
        size_bytes: Size in bytes.

    Returns:
        Formatted string like "1.23 GB", "456 KB", etc.

    Examples:
        >>> format_size(0)
        '0 B'
        >>> format_size(1024)
        '1.00 KB'
        >>> format_size(1536)
        '1.50 KB'
        >>> format_size(1073741824)
        '1.00 GB'
    """
    if size_bytes < 0:
        return "0 B"

    units = ["B", "KB", "MB", "GB", "TB", "PB"]
    unit_index = 0
    size = float(size_bytes)

    while size >= 1024.0 and unit_index < len(units) - 1:
        size /= 1024.0
        unit_index += 1

    if unit_index == 0:
        return f"{int(size)} B"
    return f"{size:.2f} {units[unit_index]}"


def format_speed(bytes_per_second: float) -> str:
    """Format transfer speed in human-readable form.

    Args:
        bytes_per_second: Speed in bytes per second.

    Returns:
        Formatted string like "12.3 MB/s".
    """
    return f"{format_size(int(bytes_per_second))}/s"


def format_duration(seconds: float) -> str:
    """Format duration in human-readable form.

    Args:
        seconds: Duration in seconds.

    Returns:
        Formatted string like "5分12秒 / 5m 12s".
    """
    if seconds < 0:
        return "0秒 / 0s"

    minutes, secs = divmod(int(seconds), 60)
    hours, minutes = divmod(minutes, 60)

    if hours > 0:
        return f"{hours}时{minutes}分{secs}秒 / {hours}h {minutes}m {secs}s"
    if minutes > 0:
        return f"{minutes}分{secs}秒 / {minutes}m {secs}s"
    return f"{secs}秒 / {secs}s"
