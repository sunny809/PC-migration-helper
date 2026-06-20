"""PC Migration Helper - Application-wide constants and enums."""

from enum import Enum, IntEnum


class FileCategory(Enum):
    """File classification categories."""
    DOCUMENTS = "documents"
    PHOTOS = "photos"
    VIDEOS = "videos"
    MUSIC = "music"
    ARCHIVES = "archives"
    BROWSER_DATA = "browser_data"
    OTHER = "other"


class MigrationFormat(Enum):
    """Supported migration output formats."""
    ZIP = "zip"
    SEVEN_ZIP = "7z"
    COPY_ONLY = "copy_only"


class ScanState(Enum):
    """Scan operation states."""
    IDLE = "idle"
    SCANNING = "scanning"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


class MigrationState(Enum):
    """Migration operation states."""
    IDLE = "idle"
    COMPRESSING = "compressing"
    COPYING = "copying"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    ERROR = "error"


# Application metadata
APP_NAME = "PC Migration Helper"
APP_NAME_ZH = "PC迁移助手"
APP_VERSION = "0.1.0"
ORGANIZATION = "PCMigration"

# Window dimensions
WINDOW_MIN_WIDTH = 1000
WINDOW_MIN_HEIGHT = 700

# File size limits
MAX_FILE_SIZE = 4 * 1024 * 1024 * 1024  # 4 GB
MIN_FILE_SIZE = 0

# I/O buffer size for copy/compression
DEFAULT_CHUNK_SIZE = 65536  # 64 KB

# Category display names (bilingual)
CATEGORY_DISPLAY = {
    FileCategory.DOCUMENTS: ("文档 / Documents", "doc"),
    FileCategory.PHOTOS: ("照片 / Photos", "img"),
    FileCategory.VIDEOS: ("视频 / Videos", "vid"),
    FileCategory.MUSIC: ("音乐 / Music", "mus"),
    FileCategory.ARCHIVES: ("压缩包 / Archives", "arc"),
    FileCategory.BROWSER_DATA: ("浏览器数据 / Browser Data", "brw"),
    FileCategory.OTHER: ("其他 / Other", "oth"),
}

# Category icons (material icon names for future use)
CATEGORY_ICONS = {
    FileCategory.DOCUMENTS: "description",
    FileCategory.PHOTOS: "image",
    FileCategory.VIDEOS: "movie",
    FileCategory.MUSIC: "music_note",
    FileCategory.ARCHIVES: "folder_zip",
    FileCategory.BROWSER_DATA: "bookmark",
    FileCategory.OTHER: "help_outline",
}
