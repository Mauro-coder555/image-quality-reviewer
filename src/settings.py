from pathlib import Path


APP_NAME = "Image Quality Reviewer"

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
TRASH_DIR = BASE_DIR / "trash"

MIN_WIDTH = 800
MIN_HEIGHT = 600

# Blur is treated as a warning, not as a critical problem.
# This avoids rejecting people photos with intentional background blur.
BLUR_THRESHOLD = 120.0

INCLUDE_SUBFOLDERS = True
MOVE_TO_TRASH_BY_DEFAULT = True

# If False, the UI only lists critical images.
# If True, the UI also lists images with warnings such as low resolution or blur.
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

# Analysis size.
# Images are sampled for speed. Originals are never modified.
ARTIFACT_ANALYSIS_MAX_SIZE = 720

# Random pixel / RGB glitch detection.
RANDOM_NOISE_COLOR_JUMP_THRESHOLD = 150
RANDOM_NOISE_MIN_COLOR_JUMP_RATIO = 0.34
RANDOM_NOISE_MIN_SATURATED_RATIO = 0.30
RANDOM_NOISE_MIN_BRIGHTNESS = 35
RANDOM_NOISE_MIN_SATURATION = 120

# Corrupted block detection.
GLITCH_GRID_SIZE = 16
DAMAGED_BLOCK_MIN_RATIO = 0.10
DAMAGED_EDGE_BLOCK_MIN_RATIO = 0.24
BLOCK_MIN_SATURATED_RATIO = 0.58
BLOCK_MIN_COLOR_JUMP_RATIO = 0.22
BLOCK_MIN_DOMINANT_RATIO = 0.82
BLOCK_MAX_FLAT_VARIANCE = 14.0

# Stripe / bar detection.
# This is stricter than the previous band detector to avoid false positives
# on portraits, studio backgrounds, logos, walls, or natural lighting.
STRIPE_SCAN_COUNT = 90
STRIPE_MIN_DOMINANT_COLOR_RATIO = 0.72
STRIPE_MAX_VARIANCE = 22.0
STRIPE_MIN_MEAN_DIFFERENCE = 70
STRIPE_MIN_SATURATED_RATIO = 0.36
STRIPE_MIN_TOTAL_RATIO = 0.035
STRIPE_MIN_GROUPS = 1
STRIPE_EDGE_ZONE_RATIO = 0.22

# Broken colored panel detection.
# Useful for images with vertical or horizontal color-tinted damaged regions.
PANEL_SCAN_COUNT = 64
PANEL_MIN_WIDTH_RATIO = 0.14
PANEL_MIN_HEIGHT_RATIO = 0.14
PANEL_MIN_SATURATED_RATIO = 0.32
PANEL_MIN_CHANNEL_SPREAD = 45
PANEL_MIN_MEAN_DIFFERENCE = 55
PANEL_EDGE_ZONE_RATIO = 0.30

# Flat edge replacement detection.
# Catches large solid-colored replacement areas on edges, but avoids flagging
# normal black backgrounds or letterboxing as critical.
EDGE_BAND_RATIO = 0.18
EDGE_BAND_MAX_VARIANCE = 18.0
EDGE_BAND_MIN_DOMINANT_RATIO = 0.78
EDGE_BAND_MIN_SATURATED_RATIO = 0.30
EDGE_BAND_MIN_MEAN_DIFFERENCE = 55

# File size warning.
# This remains a warning because highly compressed images can be valid.
MIN_BYTES_PER_MEGA_PIXEL = 18_000