from pathlib import Path


APP_NAME = "Image Quality Reviewer"

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
TRASH_DIR = BASE_DIR / "trash"

MIN_WIDTH = 800
MIN_HEIGHT = 600

# Blur is informational only. It must never reject an image.
BLUR_THRESHOLD = 120.0

INCLUDE_SUBFOLDERS = True
MOVE_TO_TRASH_BY_DEFAULT = True

# Main UI behavior:
# - Broken and suspect images are shown.
# - Warning-only images are hidden by default to avoid noise.
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

# Analysis resize limit.
# Originals are never modified.
ARTIFACT_ANALYSIS_MAX_SIZE = 900

# File checks.
MIN_FILE_SIZE_BYTES = 256
MIN_BYTES_PER_MEGA_PIXEL = 18_000

# Low information / placeholder detection.
LOW_INFORMATION_GRAY_STD = 6.0
LOW_INFORMATION_ENTROPY = 2.0
LOW_INFORMATION_UNIQUE_RATIO = 0.015

PLACEHOLDER_ENTROPY = 1.4
PLACEHOLDER_UNIQUE_RATIO = 0.008
PLACEHOLDER_EDGE_DENSITY = 0.025

# Tile / flat region checks.
TILE_GRID_SIZE = 12
FLAT_TILE_VARIANCE = 18.0
LARGE_FLAT_REGION_TILE_RATIO = 0.42

# Edge flat band checks.
EDGE_BAND_RATIO = 0.18
EDGE_FLAT_VARIANCE = 16.0
EDGE_TEXTURE_DIFFERENCE = 38.0
BOTTOM_TRUNCATION_TEXTURE_DIFFERENCE = 45.0

# Artificial band checks.
BAND_COUNT = 36
ARTIFICIAL_BAND_MIN_FLAT_RATIO = 0.18
ARTIFICIAL_BAND_MIN_TRANSITION = 48.0

# Anomalous pixels.
ANOMALOUS_PIXEL_MEDIAN_KERNEL = 5
ANOMALOUS_PIXEL_DISTANCE = 95.0
ANOMALOUS_PIXEL_RATIO = 0.02
SEVERE_ANOMALOUS_PIXEL_RATIO = 0.07

# Extreme RGB noise.
# This is the only visual signal that can become broken by itself.
EXTREME_NOISE_MIN_SATURATED_RATIO = 0.42
EXTREME_NOISE_MIN_COLOR_JUMP_RATIO = 0.34
EXTREME_NOISE_MIN_SATURATION = 135
EXTREME_NOISE_MIN_BRIGHTNESS = 45
EXTREME_NOISE_COLOR_JUMP_THRESHOLD = 165

# Color channel imbalance.
COLOR_CHANNEL_IMBALANCE_RATIO = 2.8
COLOR_CAST_MIN_SATURATION_RATIO = 0.35

# Composite scoring.
# Visual signals alone should usually become suspect, not broken.
SUSPECT_SCORE_THRESHOLD = 55
WARNING_SCORE_THRESHOLD = 15

ISSUE_WEIGHTS = {
    # Hard failures.
    "file_missing": 100,
    "file_empty": 100,
    "file_too_small": 25,
    "not_an_image": 100,
    "decode_failed": 100,
    "decode_truncated": 100,
    "invalid_dimensions": 100,

    # Structure.
    "jpeg_missing_eof": 45,
    "png_missing_iend": 50,
    "webp_size_mismatch": 45,
    "bmp_size_mismatch": 45,
    "format_extension_mismatch": 15,

    # Dimensions / metadata.
    "dimensions_too_small": 10,
    "extreme_aspect_ratio": 20,
    "suspicious_file_size": 15,

    # Visual warnings.
    "very_low_information": 25,
    "possible_placeholder": 30,
    "large_flat_regions": 5,
    "flat_edge_band": 15,
    "possible_bottom_truncation": 35,
    "artificial_horizontal_bands": 20,
    "artificial_vertical_bands": 20,
    "anomalous_pixels": 25,
    "severe_anomalous_pixels": 45,
    "color_channel_imbalance": 20,
    "extreme_rgb_noise": 100,

    # Composite.
    "composite_truncation_evidence": 100,
    "composite_visual_corruption": 55,
    "composite_placeholder_evidence": 45,
}