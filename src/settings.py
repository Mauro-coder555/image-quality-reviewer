from pathlib import Path


APP_NAME = "Image Quality Reviewer"

BASE_DIR = Path(__file__).resolve().parent.parent
REPORTS_DIR = BASE_DIR / "reports"
TRASH_DIR = BASE_DIR / "trash"
MODELS_DIR = BASE_DIR / "models"

CORRUPTION_MODEL_PATH = MODELS_DIR / "image_corruption_classifier.pt"

MIN_WIDTH = 800
MIN_HEIGHT = 600
BLUR_THRESHOLD = 120.0

INCLUDE_SUBFOLDERS = True
MOVE_TO_TRASH_BY_DEFAULT = True

# Shows broken and suspect images.
# Warning-only and info-only images stay hidden by default.
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

MIN_FILE_SIZE_BYTES = 256
MIN_BYTES_PER_MEGA_PIXEL = 18_000

# ML classifier thresholds.
# Keep these conservative to avoid false positives.
ML_SUSPECT_THRESHOLD = 0.70
ML_BROKEN_THRESHOLD = 0.97

# Scores used by the UI/report.
ISSUE_WEIGHTS = {
    "file_missing": 100,
    "file_empty": 100,
    "file_too_small": 25,
    "not_an_image": 100,
    "decode_failed": 100,
    "decode_truncated": 100,
    "invalid_dimensions": 100,

    "invalid_jpeg_header": 100,
    "jpeg_missing_eof": 65,
    "invalid_png_header": 100,
    "png_missing_iend": 65,
    "invalid_webp_header": 100,
    "webp_size_mismatch": 65,
    "invalid_bmp_header": 100,
    "bmp_size_mismatch": 65,

    "unsupported_format": 15,
    "format_extension_mismatch": 15,
    "dimensions_too_small": 5,
    "possible_blur": 0,
    "suspicious_file_size": 15,

    "ml_corruption_suspect": 70,
    "ml_corruption_broken": 100,
    "ml_model_missing": 0,
}