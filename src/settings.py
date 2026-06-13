from pathlib import Path


APP_NAME = "Image Quality Reviewer"

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
TRASH_DIR = BASE_DIR / "trash"

MIN_WIDTH = 800
MIN_HEIGHT = 600

# Lower values mean less detail was detected. This MVP uses Pillow only.
# You can tune this value after testing with your own images.
BLUR_THRESHOLD = 120.0

INCLUDE_SUBFOLDERS = True
MOVE_TO_TRASH_BY_DEFAULT = True

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}

# Used to detect image-like files that are not part of the allowed MVP formats.
KNOWN_IMAGE_EXTENSIONS = ALLOWED_EXTENSIONS | {
    ".gif",
    ".heic",
    ".heif",
    ".avif",
}

# Visual artifact detection settings.
# These are heuristics, not forensic rules.
# They help detect images that can be opened but may look damaged.
MAX_SOLID_COLOR_RATIO = 0.55
MAX_LOW_VARIANCE_BLOCK_RATIO = 0.45
LOW_VARIANCE_BLOCK_THRESHOLD = 18.0

NEAR_BLACK_THRESHOLD = 12
NEAR_WHITE_THRESHOLD = 243
MAX_GRAY_CHANNEL_DIFFERENCE = 8

MIN_BYTES_PER_MEGA_PIXEL = 25_000

ARTIFACT_ANALYSIS_MAX_SIZE = 600
ARTIFACT_GRID_SIZE = 8