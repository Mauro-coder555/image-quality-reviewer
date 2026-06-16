from pathlib import Path


APP_NAME = "Image Quality Reviewer"

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
TRASH_DIR = BASE_DIR / "trash"

MIN_WIDTH = 800
MIN_HEIGHT = 600

# Blur is informational only. It must not make an image unusable.
BLUR_THRESHOLD = 120.0

INCLUDE_SUBFOLDERS = True
MOVE_TO_TRASH_BY_DEFAULT = True

# Keep False to show only images that are very likely unusable.
SHOW_WARNINGS_IN_UI = False

ALLOWED_EXTENSIONS = {
    ".jpg",
    ".jpeg",
    ".png",
    ".webp",
    ".bmp",
    ".tif",
    ".tiff",
}

KNOWN_IMAGE_EXTENSIONS = ALLOWED_EXTENSIONS | {
    ".gif",
    ".heic",
    ".heif",
    ".avif",
}

CHECK_FORMAT_EXTENSION_MISMATCH = True

EXTENSION_TO_PIL_FORMATS = {
    ".jpg": {"JPEG"},
    ".jpeg": {"JPEG"},
    ".png": {"PNG"},
    ".webp": {"WEBP"},
    ".bmp": {"BMP"},
    ".tif": {"TIFF"},
    ".tiff": {"TIFF"},
}

# OpenCV-based corruption detection.
# The goal is to flag only images that are truly broken or unusable.
ARTIFACT_ANALYSIS_MAX_SIZE = 720

# Score needed to mark visual corruption as critical.
# Individual weak signals become warnings only.
UNUSABLE_SCORE_THRESHOLD = 3.0

# Extreme RGB noise.
EXTREME_NOISE_SCORE = 4.0
EXTREME_NOISE_MIN_SATURATED_RATIO = 0.34
EXTREME_NOISE_MIN_COLOR_JUMP_RATIO = 0.28
EXTREME_NOISE_MIN_SATURATION = 125
EXTREME_NOISE_MIN_BRIGHTNESS = 40
EXTREME_NOISE_COLOR_JUMP_THRESHOLD = 145

# Large damaged panel + seam.
PANEL_DAMAGE_SCORE = 2.0
PANEL_SCAN_RATIO = 0.28
PANEL_MIN_CONTEXT_DIFFERENCE = 48.0
PANEL_MIN_SATURATED_RATIO = 0.18
PANEL_MIN_SEAM_DIFFERENCE = 42.0

# Global seam / split image.
GLOBAL_SEAM_SCORE = 1.5
GLOBAL_SEAM_MIN_DIFFERENCE = 48.0
GLOBAL_SEAM_OUTLIER_MULTIPLIER = 2.8
GLOBAL_SEAM_EDGE_IGNORE_RATIO = 0.08

# Solid replacement edge.
SOLID_EDGE_REPLACEMENT_SCORE = 3.0
SOLID_EDGE_RATIO = 0.24
SOLID_EDGE_MIN_DOMINANT_RATIO = 0.84
SOLID_EDGE_MAX_GRAY_VARIANCE = 16.0
SOLID_EDGE_MIN_CONTEXT_DIFFERENCE = 58.0

# Damaged block mosaic.
DAMAGED_BLOCKS_SCORE = 2.0
DAMAGED_BLOCK_GRID_SIZE = 12
DAMAGED_BLOCK_MIN_RATIO = 0.16
DAMAGED_BLOCK_MIN_SATURATED_RATIO = 0.48
DAMAGED_BLOCK_MIN_COLOR_JUMP_RATIO = 0.22

# Warning-only checks.
MIN_BYTES_PER_MEGA_PIXEL = 18_000