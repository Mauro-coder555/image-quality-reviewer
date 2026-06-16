from dataclasses import dataclass, field
from pathlib import Path
from typing import BinaryIO

from PIL import Image, ImageFilter, ImageStat, UnidentifiedImageError

from src.settings import (
    ALLOWED_EXTENSIONS,
    ARTIFACT_ANALYSIS_MAX_SIZE,
    BLOCK_MAX_FLAT_VARIANCE,
    BLOCK_MIN_COLOR_JUMP_RATIO,
    BLOCK_MIN_DOMINANT_RATIO,
    BLOCK_MIN_SATURATED_RATIO,
    BLUR_THRESHOLD,
    CHECK_FORMAT_EXTENSION_MISMATCH,
    DAMAGED_BLOCK_MIN_RATIO,
    DAMAGED_EDGE_BLOCK_MIN_RATIO,
    EDGE_BAND_MAX_VARIANCE,
    EDGE_BAND_MIN_DOMINANT_RATIO,
    EDGE_BAND_MIN_MEAN_DIFFERENCE,
    EDGE_BAND_MIN_SATURATED_RATIO,
    EDGE_BAND_RATIO,
    EXTENSION_TO_PIL_FORMATS,
    GLITCH_GRID_SIZE,
    MIN_BYTES_PER_MEGA_PIXEL,
    MIN_HEIGHT,
    MIN_WIDTH,
    PANEL_EDGE_ZONE_RATIO,
    PANEL_MIN_CHANNEL_SPREAD,
    PANEL_MIN_HEIGHT_RATIO,
    PANEL_MIN_MEAN_DIFFERENCE,
    PANEL_MIN_SATURATED_RATIO,
    PANEL_MIN_WIDTH_RATIO,
    PANEL_SCAN_COUNT,
    RANDOM_NOISE_COLOR_JUMP_THRESHOLD,
    RANDOM_NOISE_MIN_BRIGHTNESS,
    RANDOM_NOISE_MIN_COLOR_JUMP_RATIO,
    RANDOM_NOISE_MIN_SATURATED_RATIO,
    RANDOM_NOISE_MIN_SATURATION,
    STRIPE_EDGE_ZONE_RATIO,
    STRIPE_MAX_VARIANCE,
    STRIPE_MIN_DOMINANT_COLOR_RATIO,
    STRIPE_MIN_GROUPS,
    STRIPE_MIN_MEAN_DIFFERENCE,
    STRIPE_MIN_SATURATED_RATIO,
    STRIPE_MIN_TOTAL_RATIO,
    STRIPE_SCAN_COUNT,
)


@dataclass
class ImageAnalysisResult:
    path: Path
    is_problematic: bool
    critical_reasons: list[str] = field(default_factory=list)
    warning_reasons: list[str] = field(default_factory=list)
    info_reasons: list[str] = field(default_factory=list)
    width: int | None = None
    height: int | None = None
    blur_score: float | None = None
    status: str = "pending"
    marked_for_deletion: bool = False

    @property
    def severity(self) -> str:
        if self.critical_reasons:
            return "critical"
        if self.warning_reasons:
            return "warning"
        if self.info_reasons:
            return "info"
        return "ok"

    @property
    def reasons(self) -> list[str]:
        return self.critical_reasons + self.warning_reasons + self.info_reasons


def analyze_image(path: Path) -> ImageAnalysisResult:
    result = ImageAnalysisResult(
        path=path,
        is_problematic=False,
        status="analyzed",
    )

    if path.suffix.lower() not in ALLOWED_EXTENSIONS:
        result.warning_reasons.append("Unsupported image format")
        result.status = "warning"
        return result

    if not path.exists():
        result.critical_reasons.append("File does not exist")
        result.is_problematic = True
        result.status = "critical"
        return result

    try:
        result.critical_reasons.extend(detect_file_structure_issues(path))

        verify_image_file(path)

        width, height, image_format, blur_score, critical_artifacts, warnings = inspect_image_file(path)

        result.width = width
        result.height = height
        result.blur_score = blur_score

        if width <= 0 or height <= 0:
            result.critical_reasons.append("Invalid image dimensions")

        if width < MIN_WIDTH or height < MIN_HEIGHT:
            result.warning_reasons.append(f"Low resolution: {width}x{height}")

        if blur_score < BLUR_THRESHOLD:
            result.warning_reasons.append(f"Possible blur detected: score {blur_score:.2f}")

        result.warning_reasons.extend(
            detect_format_extension_mismatch(path=path, image_format=image_format)
        )

        result.critical_reasons.extend(critical_artifacts)
        result.warning_reasons.extend(warnings)

        result.critical_reasons = remove_duplicate_reasons(result.critical_reasons)
        result.warning_reasons = remove_duplicate_reasons(result.warning_reasons)

        result.is_problematic = bool(result.critical_reasons)
        result.status = result.severity

    except UnidentifiedImageError:
        result.critical_reasons.append("Image cannot be opened")
        result.is_problematic = True
        result.status = "critical"

    except OSError as error:
        result.critical_reasons.append(f"Read error or possibly incomplete file: {error}")
        result.is_problematic = True
        result.status = "critical"

    except Exception as error:
        result.critical_reasons.append(f"Unexpected analysis error: {error}")
        result.is_problematic = True
        result.status = "critical"

    return result


def verify_image_file(path: Path) -> None:
    with Image.open(path) as image:
        image.verify()


def inspect_image_file(path: Path) -> tuple[int, int, str | None, float, list[str], list[str]]:
    with Image.open(path) as image:
        image.load()

        width, height = image.size
        image_format = image.format
        blur_score = calculate_blur_score(image)

        sample_image = build_sample_image(image)

        critical_artifacts = detect_severe_visual_damage(sample_image)
        warnings = detect_non_critical_quality_warnings(
            file_path=path,
            width=width,
            height=height,
        )

        return width, height, image_format, blur_score, critical_artifacts, warnings


def calculate_blur_score(image: Image.Image) -> float:
    grayscale_image = image.convert("L")
    grayscale_image.thumbnail((800, 800))

    edge_image = grayscale_image.filter(ImageFilter.FIND_EDGES)
    stat = ImageStat.Stat(edge_image)

    return float(stat.var[0])


def detect_file_structure_issues(path: Path) -> list[str]:
    reasons: list[str] = []

    try:
        file_size = path.stat().st_size
    except OSError:
        return ["File size could not be read"]

    if file_size == 0:
        return ["Empty file"]

    suffix = path.suffix.lower()

    try:
        with path.open("rb") as file:
            if suffix in {".jpg", ".jpeg"}:
                reasons.extend(validate_jpeg_structure(file, file_size))
            elif suffix == ".png":
                reasons.extend(validate_png_structure(file, file_size))
            elif suffix == ".webp":
                reasons.extend(validate_webp_structure(file, file_size))
            elif suffix == ".bmp":
                reasons.extend(validate_bmp_structure(file, file_size))
    except OSError as error:
        reasons.append(f"File structure could not be checked: {error}")

    return reasons


def validate_jpeg_structure(file: BinaryIO, file_size: int) -> list[str]:
    if file_size < 4:
        return ["Possible incomplete JPEG file: file is too small"]

    reasons: list[str] = []

    file.seek(0)
    start_bytes = file.read(2)

    file.seek(-2, 2)
    end_bytes = file.read(2)

    if start_bytes != b"\xff\xd8":
        reasons.append("Invalid JPEG header")

    if end_bytes != b"\xff\xd9":
        reasons.append("Possible incomplete JPEG file: missing end marker")

    return reasons


def validate_png_structure(file: BinaryIO, file_size: int) -> list[str]:
    png_signature = b"\x89PNG\r\n\x1a\n"

    if file_size < len(png_signature) + 12:
        return ["Possible incomplete PNG file: file is too small"]

    reasons: list[str] = []

    file.seek(0)
    start_bytes = file.read(len(png_signature))

    if start_bytes != png_signature:
        reasons.append("Invalid PNG header")

    file.seek(-12, 2)
    ending_chunk = file.read(12)

    if b"IEND" not in ending_chunk:
        reasons.append("Possible incomplete PNG file: missing IEND chunk")

    return reasons


def validate_webp_structure(file: BinaryIO, file_size: int) -> list[str]:
    if file_size < 12:
        return ["Possible incomplete WEBP file: file is too small"]

    reasons: list[str] = []

    file.seek(0)
    header = file.read(12)

    if not header.startswith(b"RIFF") or header[8:12] != b"WEBP":
        reasons.append("Invalid WEBP header")
        return reasons

    declared_size = int.from_bytes(header[4:8], byteorder="little", signed=False) + 8

    if declared_size > file_size + 2:
        reasons.append("Possible incomplete WEBP file: declared size is larger than actual file size")

    return reasons


def validate_bmp_structure(file: BinaryIO, file_size: int) -> list[str]:
    if file_size < 26:
        return ["Possible incomplete BMP file: file is too small"]

    reasons: list[str] = []

    file.seek(0)
    header = file.read(6)

    if not header.startswith(b"BM"):
        reasons.append("Invalid BMP header")
        return reasons

    declared_size = int.from_bytes(header[2:6], byteorder="little", signed=False)

    if declared_size > 0 and declared_size > file_size:
        reasons.append("Possible incomplete BMP file: declared size is larger than actual file size")

    return reasons


def detect_format_extension_mismatch(path: Path, image_format: str | None) -> list[str]:
    if not CHECK_FORMAT_EXTENSION_MISMATCH:
        return []

    if image_format is None:
        return []

    expected_formats = EXTENSION_TO_PIL_FORMATS.get(path.suffix.lower())

    if not expected_formats:
        return []

    if image_format.upper() not in expected_formats:
        return [
            f"Format mismatch: file extension is {path.suffix.lower()} "
            f"but detected format is {image_format}"
        ]

    return []


def detect_severe_visual_damage(image: Image.Image) -> list[str]:
    reasons: list[str] = []

    reasons.extend(detect_random_pixel_noise(image))
    reasons.extend(detect_corrupted_blocks(image))
    reasons.extend(detect_colored_stripe_artifacts(image))
    reasons.extend(detect_flat_colored_edge_replacements(image))
    reasons.extend(detect_broken_colored_panels(image))

    return remove_duplicate_reasons(reasons)


def detect_random_pixel_noise(image: Image.Image) -> list[str]:
    rgb_image = image.convert("RGB")
    hsv_image = image.convert("HSV")

    saturated_ratio = calculate_saturated_ratio(
        hsv_image,
        min_saturation=RANDOM_NOISE_MIN_SATURATION,
        min_brightness=RANDOM_NOISE_MIN_BRIGHTNESS,
    )
    color_jump_ratio = calculate_color_jump_ratio(
        rgb_image,
        threshold=RANDOM_NOISE_COLOR_JUMP_THRESHOLD,
    )

    if (
        saturated_ratio >= RANDOM_NOISE_MIN_SATURATED_RATIO
        and color_jump_ratio >= RANDOM_NOISE_MIN_COLOR_JUMP_RATIO
    ):
        return [
            f"Severe pixel noise or RGB glitch detected "
            f"(saturation {saturated_ratio:.0%}, color jumps {color_jump_ratio:.0%})"
        ]

    return []


def detect_corrupted_blocks(image: Image.Image) -> list[str]:
    rgb_image = image.convert("RGB")
    hsv_image = image.convert("HSV")
    gray_image = image.convert("L")

    rgb_blocks = crop_grid_blocks(rgb_image, GLITCH_GRID_SIZE)
    hsv_blocks = crop_grid_blocks(hsv_image, GLITCH_GRID_SIZE)
    gray_blocks = crop_grid_blocks(gray_image, GLITCH_GRID_SIZE)

    if not rgb_blocks or not hsv_blocks or not gray_blocks:
        return []

    damaged_blocks = 0
    damaged_edge_blocks = 0
    total_blocks = len(rgb_blocks)
    edge_blocks = 0

    for index, block_group in enumerate(zip(rgb_blocks, hsv_blocks, gray_blocks)):
        rgb_block, hsv_block, gray_block = block_group

        row = index // GLITCH_GRID_SIZE
        column = index % GLITCH_GRID_SIZE

        is_edge_block = (
            row == 0
            or column == 0
            or row == GLITCH_GRID_SIZE - 1
            or column == GLITCH_GRID_SIZE - 1
        )

        if is_edge_block:
            edge_blocks += 1

        saturated_ratio = calculate_saturated_ratio(
            hsv_block,
            min_saturation=RANDOM_NOISE_MIN_SATURATION,
            min_brightness=RANDOM_NOISE_MIN_BRIGHTNESS,
        )
        color_jump_ratio = calculate_color_jump_ratio(
            rgb_block,
            threshold=RANDOM_NOISE_COLOR_JUMP_THRESHOLD,
        )
        variance = float(ImageStat.Stat(gray_block).var[0])
        dominant_ratio = calculate_dominant_color_ratio(rgb_block)

        is_noisy_damaged_block = (
            saturated_ratio >= BLOCK_MIN_SATURATED_RATIO
            and color_jump_ratio >= BLOCK_MIN_COLOR_JUMP_RATIO
        )

        is_flat_replacement_block = (
            dominant_ratio >= BLOCK_MIN_DOMINANT_RATIO
            and variance <= BLOCK_MAX_FLAT_VARIANCE
            and saturated_ratio >= 0.18
        )

        if is_noisy_damaged_block or is_flat_replacement_block:
            damaged_blocks += 1

            if is_edge_block:
                damaged_edge_blocks += 1

    damaged_block_ratio = damaged_blocks / total_blocks
    damaged_edge_ratio = damaged_edge_blocks / edge_blocks if edge_blocks else 0.0

    reasons: list[str] = []

    if damaged_block_ratio >= DAMAGED_BLOCK_MIN_RATIO:
        reasons.append(f"Severe block corruption detected ({damaged_block_ratio:.0%} damaged blocks)")

    if damaged_edge_ratio >= DAMAGED_EDGE_BLOCK_MIN_RATIO:
        reasons.append(f"Possible edge corruption detected ({damaged_edge_ratio:.0%} damaged edge blocks)")

    return reasons


def detect_colored_stripe_artifacts(image: Image.Image) -> list[str]:
    reasons: list[str] = []

    horizontal_result = analyze_colored_stripes(image, orientation="horizontal")
    vertical_result = analyze_colored_stripes(image, orientation="vertical")

    if horizontal_result is not None:
        ratio, group_count = horizontal_result
        reasons.append(
            f"Strong colored horizontal stripe artifact detected "
            f"({ratio:.0%} suspicious stripes, {group_count} group(s))"
        )

    if vertical_result is not None:
        ratio, group_count = vertical_result
        reasons.append(
            f"Strong colored vertical stripe artifact detected "
            f"({ratio:.0%} suspicious stripes, {group_count} group(s))"
        )

    return reasons


def analyze_colored_stripes(image: Image.Image, orientation: str) -> tuple[float, int] | None:
    rgb_image = image.convert("RGB")
    hsv_image = image.convert("HSV")
    gray_image = image.convert("L")

    width, height = rgb_image.size

    if width <= 0 or height <= 0:
        return None

    suspicious_indexes: list[int] = []
    band_stats = []

    for index in range(STRIPE_SCAN_COUNT):
        if orientation == "horizontal":
            start = int(index * height / STRIPE_SCAN_COUNT)
            end = int((index + 1) * height / STRIPE_SCAN_COUNT)
            rgb_band = rgb_image.crop((0, start, width, end))
            hsv_band = hsv_image.crop((0, start, width, end))
            gray_band = gray_image.crop((0, start, width, end))
        else:
            start = int(index * width / STRIPE_SCAN_COUNT)
            end = int((index + 1) * width / STRIPE_SCAN_COUNT)
            rgb_band = rgb_image.crop((start, 0, end, height))
            hsv_band = hsv_image.crop((start, 0, end, height))
            gray_band = gray_image.crop((start, 0, end, height))

        if rgb_band.size[0] <= 0 or rgb_band.size[1] <= 0:
            continue

        mean = tuple(ImageStat.Stat(rgb_band).mean[:3])
        variance = float(ImageStat.Stat(gray_band).var[0])
        dominant_ratio = calculate_dominant_color_ratio(rgb_band)
        saturated_ratio = calculate_saturated_ratio(
            hsv_band,
            min_saturation=RANDOM_NOISE_MIN_SATURATION,
            min_brightness=RANDOM_NOISE_MIN_BRIGHTNESS,
        )

        band_stats.append(
            {
                "index": index,
                "mean": mean,
                "variance": variance,
                "dominant_ratio": dominant_ratio,
                "saturated_ratio": saturated_ratio,
            }
        )

    if len(band_stats) < 3:
        return None

    for position in range(1, len(band_stats) - 1):
        current = band_stats[position]
        previous_band = band_stats[position - 1]
        next_band = band_stats[position + 1]

        previous_diff = color_mean_distance(current["mean"], previous_band["mean"])
        next_diff = color_mean_distance(current["mean"], next_band["mean"])
        mean_difference = max(previous_diff, next_diff)

        is_flat_colored_stripe = (
            current["dominant_ratio"] >= STRIPE_MIN_DOMINANT_COLOR_RATIO
            and current["variance"] <= STRIPE_MAX_VARIANCE
            and current["saturated_ratio"] >= STRIPE_MIN_SATURATED_RATIO
            and mean_difference >= STRIPE_MIN_MEAN_DIFFERENCE
        )

        if is_flat_colored_stripe:
            suspicious_indexes.append(current["index"])

    if not suspicious_indexes:
        return None

    suspicious_ratio = len(suspicious_indexes) / STRIPE_SCAN_COUNT
    groups = group_consecutive_indexes(suspicious_indexes)
    group_count = len(groups)

    has_edge_group = any(is_group_near_edge(group, STRIPE_SCAN_COUNT, STRIPE_EDGE_ZONE_RATIO) for group in groups)

    if suspicious_ratio >= STRIPE_MIN_TOTAL_RATIO and (
        group_count >= STRIPE_MIN_GROUPS or has_edge_group
    ):
        return suspicious_ratio, group_count

    return None


def detect_flat_colored_edge_replacements(image: Image.Image) -> list[str]:
    rgb_image = image.convert("RGB")
    hsv_image = image.convert("HSV")
    gray_image = image.convert("L")

    width, height = rgb_image.size

    if width <= 0 or height <= 0:
        return []

    band_height = max(1, int(height * EDGE_BAND_RATIO))
    band_width = max(1, int(width * EDGE_BAND_RATIO))

    bands = {
        "top": (
            rgb_image.crop((0, 0, width, band_height)),
            hsv_image.crop((0, 0, width, band_height)),
            gray_image.crop((0, 0, width, band_height)),
            rgb_image.crop((0, band_height, width, min(height, band_height * 2))),
        ),
        "bottom": (
            rgb_image.crop((0, height - band_height, width, height)),
            hsv_image.crop((0, height - band_height, width, height)),
            gray_image.crop((0, height - band_height, width, height)),
            rgb_image.crop((0, max(0, height - band_height * 2), width, height - band_height)),
        ),
        "left": (
            rgb_image.crop((0, 0, band_width, height)),
            hsv_image.crop((0, 0, band_width, height)),
            gray_image.crop((0, 0, band_width, height)),
            rgb_image.crop((band_width, 0, min(width, band_width * 2), height)),
        ),
        "right": (
            rgb_image.crop((width - band_width, 0, width, height)),
            hsv_image.crop((width - band_width, 0, width, height)),
            gray_image.crop((width - band_width, 0, width, height)),
            rgb_image.crop((max(0, width - band_width * 2), 0, width - band_width, height)),
        ),
    }

    damaged_edges: list[str] = []

    for name, band_group in bands.items():
        rgb_band, hsv_band, gray_band, adjacent_band = band_group

        variance = float(ImageStat.Stat(gray_band).var[0])
        dominant_ratio = calculate_dominant_color_ratio(rgb_band)
        saturated_ratio = calculate_saturated_ratio(
            hsv_band,
            min_saturation=RANDOM_NOISE_MIN_SATURATION,
            min_brightness=RANDOM_NOISE_MIN_BRIGHTNESS,
        )
        mean_difference = color_mean_distance(
            tuple(ImageStat.Stat(rgb_band).mean[:3]),
            tuple(ImageStat.Stat(adjacent_band).mean[:3]),
        )

        is_colored_flat_replacement = (
            variance <= EDGE_BAND_MAX_VARIANCE
            and dominant_ratio >= EDGE_BAND_MIN_DOMINANT_RATIO
            and saturated_ratio >= EDGE_BAND_MIN_SATURATED_RATIO
            and mean_difference >= EDGE_BAND_MIN_MEAN_DIFFERENCE
        )

        if is_colored_flat_replacement:
            damaged_edges.append(name)

    if damaged_edges:
        return [
            f"Possible partial image decode failure: colored flat replacement on "
            f"{', '.join(damaged_edges)} edge"
        ]

    return []


def detect_broken_colored_panels(image: Image.Image) -> list[str]:
    reasons: list[str] = []

    vertical_panel = analyze_tinted_panels(image, orientation="vertical")
    horizontal_panel = analyze_tinted_panels(image, orientation="horizontal")

    if vertical_panel is not None:
        ratio, side = vertical_panel
        reasons.append(f"Broken colored vertical panel detected on {side} area ({ratio:.0%} of image width)")

    if horizontal_panel is not None:
        ratio, side = horizontal_panel
        reasons.append(f"Broken colored horizontal panel detected on {side} area ({ratio:.0%} of image height)")

    return reasons


def analyze_tinted_panels(image: Image.Image, orientation: str) -> tuple[float, str] | None:
    rgb_image = image.convert("RGB")
    hsv_image = image.convert("HSV")

    width, height = rgb_image.size

    if width <= 0 or height <= 0:
        return None

    center_mean = calculate_center_mean(rgb_image)
    suspicious_indexes: list[int] = []

    for index in range(PANEL_SCAN_COUNT):
        if orientation == "vertical":
            start = int(index * width / PANEL_SCAN_COUNT)
            end = int((index + 1) * width / PANEL_SCAN_COUNT)
            rgb_panel = rgb_image.crop((start, 0, end, height))
            hsv_panel = hsv_image.crop((start, 0, end, height))
        else:
            start = int(index * height / PANEL_SCAN_COUNT)
            end = int((index + 1) * height / PANEL_SCAN_COUNT)
            rgb_panel = rgb_image.crop((0, start, width, end))
            hsv_panel = hsv_image.crop((0, start, width, end))

        if rgb_panel.size[0] <= 0 or rgb_panel.size[1] <= 0:
            continue

        mean = tuple(ImageStat.Stat(rgb_panel).mean[:3])
        saturated_ratio = calculate_saturated_ratio(
            hsv_panel,
            min_saturation=RANDOM_NOISE_MIN_SATURATION,
            min_brightness=RANDOM_NOISE_MIN_BRIGHTNESS,
        )
        channel_spread = max(mean) - min(mean)
        mean_difference = color_mean_distance(mean, center_mean)

        is_tinted_panel = (
            saturated_ratio >= PANEL_MIN_SATURATED_RATIO
            and channel_spread >= PANEL_MIN_CHANNEL_SPREAD
            and mean_difference >= PANEL_MIN_MEAN_DIFFERENCE
        )

        if is_tinted_panel:
            suspicious_indexes.append(index)

    if not suspicious_indexes:
        return None

    groups = group_consecutive_indexes(suspicious_indexes)

    for group in groups:
        group_ratio = len(group) / PANEL_SCAN_COUNT

        if orientation == "vertical":
            minimum_ratio = PANEL_MIN_WIDTH_RATIO
        else:
            minimum_ratio = PANEL_MIN_HEIGHT_RATIO

        if group_ratio < minimum_ratio:
            continue

        if is_group_near_edge(group, PANEL_SCAN_COUNT, PANEL_EDGE_ZONE_RATIO):
            side = get_group_side(group, PANEL_SCAN_COUNT, orientation)
            return group_ratio, side

    return None


def detect_non_critical_quality_warnings(
    file_path: Path,
    width: int,
    height: int,
) -> list[str]:
    warnings: list[str] = []

    warnings.extend(detect_suspicious_file_size(file_path, width, height))

    return warnings


def detect_suspicious_file_size(file_path: Path, width: int, height: int) -> list[str]:
    if width <= 0 or height <= 0:
        return []

    try:
        file_size_bytes = file_path.stat().st_size
    except OSError:
        return ["File size could not be read"]

    mega_pixels = (width * height) / 1_000_000

    if mega_pixels <= 0:
        return []

    bytes_per_mega_pixel = file_size_bytes / mega_pixels

    if bytes_per_mega_pixel < MIN_BYTES_PER_MEGA_PIXEL:
        return [
            f"Suspiciously small file size for dimensions "
            f"({bytes_per_mega_pixel:.0f} bytes per megapixel)"
        ]

    return []


def calculate_saturated_ratio(
    image: Image.Image,
    min_saturation: int,
    min_brightness: int,
) -> float:
    hsv_image = image.convert("HSV")
    pixels = list(hsv_image.getdata())

    if not pixels:
        return 0.0

    saturated_pixels = 0

    for hue, saturation, value in pixels:
        if saturation >= min_saturation and value >= min_brightness:
            saturated_pixels += 1

    return saturated_pixels / len(pixels)


def calculate_color_jump_ratio(image: Image.Image, threshold: int) -> float:
    rgb_image = image.convert("RGB")
    width, height = rgb_image.size

    if width < 2 or height < 2:
        return 0.0

    pixels = rgb_image.load()
    comparisons = 0
    jumps = 0

    step_x = max(1, width // 240)
    step_y = max(1, height // 240)

    for y in range(0, height - 1, step_y):
        for x in range(0, width - 1, step_x):
            current_pixel = pixels[x, y]
            right_pixel = pixels[x + 1, y]
            bottom_pixel = pixels[x, y + 1]

            if color_distance(current_pixel, right_pixel) >= threshold:
                jumps += 1

            if color_distance(current_pixel, bottom_pixel) >= threshold:
                jumps += 1

            comparisons += 2

    if comparisons == 0:
        return 0.0

    return jumps / comparisons


def calculate_dominant_color_ratio(image: Image.Image) -> float:
    sample = image.copy()
    sample.thumbnail((180, 180))
    quantized = sample.convert("P", palette=Image.ADAPTIVE, colors=8)

    histogram = quantized.histogram()
    total_pixels = sum(histogram)

    if total_pixels == 0:
        return 0.0

    return max(histogram) / total_pixels


def calculate_center_mean(image: Image.Image) -> tuple[float, float, float]:
    width, height = image.size

    left = int(width * 0.35)
    right = int(width * 0.65)
    upper = int(height * 0.35)
    lower = int(height * 0.65)

    center = image.crop((left, upper, right, lower))

    return tuple(ImageStat.Stat(center).mean[:3])


def color_distance(first_pixel: tuple[int, int, int], second_pixel: tuple[int, int, int]) -> float:
    red_diff = first_pixel[0] - second_pixel[0]
    green_diff = first_pixel[1] - second_pixel[1]
    blue_diff = first_pixel[2] - second_pixel[2]

    return (red_diff * red_diff + green_diff * green_diff + blue_diff * blue_diff) ** 0.5


def color_mean_distance(
    first_mean: tuple[float, float, float],
    second_mean: tuple[float, float, float],
) -> float:
    red_diff = first_mean[0] - second_mean[0]
    green_diff = first_mean[1] - second_mean[1]
    blue_diff = first_mean[2] - second_mean[2]

    return (red_diff * red_diff + green_diff * green_diff + blue_diff * blue_diff) ** 0.5


def build_sample_image(image: Image.Image) -> Image.Image:
    sample_image = image.copy()
    sample_image.thumbnail((ARTIFACT_ANALYSIS_MAX_SIZE, ARTIFACT_ANALYSIS_MAX_SIZE))
    return sample_image


def crop_grid_blocks(image: Image.Image, grid_size: int) -> list[Image.Image]:
    width, height = image.size

    if width < grid_size or height < grid_size:
        return []

    block_width = max(1, width // grid_size)
    block_height = max(1, height // grid_size)

    blocks: list[Image.Image] = []

    for row in range(grid_size):
        for column in range(grid_size):
            left = column * block_width
            upper = row * block_height
            right = width if column == grid_size - 1 else left + block_width
            lower = height if row == grid_size - 1 else upper + block_height

            blocks.append(image.crop((left, upper, right, lower)))

    return blocks


def group_consecutive_indexes(indexes: list[int]) -> list[list[int]]:
    if not indexes:
        return []

    sorted_indexes = sorted(indexes)
    groups: list[list[int]] = [[sorted_indexes[0]]]

    for index in sorted_indexes[1:]:
        current_group = groups[-1]

        if index == current_group[-1] + 1:
            current_group.append(index)
        else:
            groups.append([index])

    return groups


def is_group_near_edge(group: list[int], total_count: int, edge_zone_ratio: float) -> bool:
    if not group:
        return False

    edge_limit = int(total_count * edge_zone_ratio)

    return min(group) <= edge_limit or max(group) >= total_count - edge_limit


def get_group_side(group: list[int], total_count: int, orientation: str) -> str:
    group_center = (min(group) + max(group)) / 2
    total_center = total_count / 2

    if orientation == "vertical":
        return "left" if group_center < total_center else "right"

    return "top" if group_center < total_center else "bottom"


def remove_duplicate_reasons(reasons: list[str]) -> list[str]:
    seen: set[str] = set()
    unique_reasons: list[str] = []

    for reason in reasons:
        if reason not in seen:
            unique_reasons.append(reason)
            seen.add(reason)

    return unique_reasons