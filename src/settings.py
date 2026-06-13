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