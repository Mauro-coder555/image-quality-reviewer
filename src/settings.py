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

# Keep False to show only images classified as Unusable.
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

# Dataset mode.
# When enabled, the detector avoids rejecting valid people photos because of
# backgrounds, banners, fabrics, signs, blur, walls, or event lights.
PEOPLE_DATASET_MODE = True

# OpenCV-based corruption detection.
ARTIFACT_ANALYSIS_MAX_SIZE = 720

# Face detection.
FACE_DETECTION_SCALE_FACTOR = 1.08
FACE_DETECTION_MIN_NEIGHBORS = 5
FACE_MIN_AREA_RATIO = 0.006
FACE_EDGE_MARGIN_RATIO = 0.04

# Critical direct detection.
# These signals are strong enough to mark an image as unusable even if a face exists.
EXTREME_NOISE_MIN_SATURATED_RATIO = 0.42
EXTREME_NOISE_MIN_COLOR_JUMP_RATIO = 0.34
EXTREME_NOISE_MIN_SATURATION = 135
EXTREME_NOISE_MIN_BRIGHTNESS = 45
EXTREME_NOISE_COLOR_JUMP_THRESHOLD = 165

SOLID_EDGE_RATIO = 0.25
SOLID_EDGE_MIN_DOMINANT_RATIO = 0.90
SOLID_EDGE_MAX_GRAY_VARIANCE = 10.0
SOLID_EDGE_MIN_CONTEXT_DIFFERENCE = 72.0
SOLID_EDGE_MIN_SATURATED_RATIO = 0.18

# Visual damage signals.
# In people dataset mode, these are only critical when there is no reliable face.
GLOBAL_SEAM_MIN_DIFFERENCE = 50.0
GLOBAL_SEAM_OUTLIER_MULTIPLIER = 3.0
GLOBAL_SEAM_EDGE_IGNORE_RATIO = 0.10

PANEL_SCAN_RATIO = 0.30
PANEL_MIN_CONTEXT_DIFFERENCE = 54.0
PANEL_MIN_SATURATED_RATIO = 0.22
PANEL_MIN_SEAM_DIFFERENCE = 48.0

DAMAGED_BLOCK_GRID_SIZE = 12
DAMAGED_BLOCK_MIN_RATIO = 0.20
DAMAGED_BLOCK_MIN_SATURATED_RATIO = 0.52
DAMAGED_BLOCK_MIN_COLOR_JUMP_RATIO = 0.24

# If no reliable face is detected, visual damage signals can become critical.
NO_FACE_VISUAL_DAMAGE_SCORE_THRESHOLD = 2.0

PANEL_DAMAGE_SCORE = 2.0
GLOBAL_SEAM_SCORE = 1.5
DAMAGED_BLOCKS_SCORE = 2.0

# Warning-only checks.
MIN_BYTES_PER_MEGA_PIXEL = 18_000