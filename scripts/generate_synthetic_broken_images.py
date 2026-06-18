from pathlib import Path
import random
from typing import Callable

import cv2
import numpy as np
from PIL import Image, ImageEnhance


PROJECT_ROOT = Path(__file__).resolve().parent.parent
SOURCE_OK_DIR = PROJECT_ROOT / "training_data" / "ok"
OUTPUT_BROKEN_DIR = PROJECT_ROOT / "training_data" / "broken"

SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp", ".bmp"}

VARIANTS_PER_IMAGE = 5
RANDOM_SEED = 42


def main() -> None:
    random.seed(RANDOM_SEED)
    np.random.seed(RANDOM_SEED)

    OUTPUT_BROKEN_DIR.mkdir(parents=True, exist_ok=True)

    source_images = find_images(SOURCE_OK_DIR)

    if not source_images:
        raise ValueError(f"No source images found in {SOURCE_OK_DIR}")

    corruptions: list[Callable[[Image.Image], Image.Image]] = [
        corrupt_bottom_truncation,
        corrupt_top_truncation,
        corrupt_left_panel,
        corrupt_right_panel,
        corrupt_random_color_blocks,
        corrupt_horizontal_bands,
        corrupt_vertical_bands,
        corrupt_channel_shift,
        corrupt_missing_color_channel,
        corrupt_hot_pixels,
        corrupt_jpeg_degradation,
        corrupt_partial_gray_panel,
        corrupt_green_or_magenta_panel,
        corrupt_block_shuffle,
    ]

    saved_count = 0

    for source_path in source_images:
        with Image.open(source_path) as image:
            image = image.convert("RGB")

        selected_corruptions = random.sample(
            corruptions,
            k=min(VARIANTS_PER_IMAGE, len(corruptions)),
        )

        for corruption_function in selected_corruptions:
            corrupted = corruption_function(image.copy())

            output_path = OUTPUT_BROKEN_DIR / (
                f"synthetic_{source_path.stem}_{corruption_function.__name__}_{saved_count:05d}.jpg"
            )

            corrupted.save(output_path, format="JPEG", quality=92)
            saved_count += 1

            if saved_count % 100 == 0:
                print(f"Generated {saved_count} synthetic broken images...")

    print(f"Done. Generated {saved_count} images in {OUTPUT_BROKEN_DIR}")


def find_images(folder: Path) -> list[Path]:
    return sorted(
        path
        for path in folder.rglob("*")
        if path.is_file() and path.suffix.lower() in SUPPORTED_EXTENSIONS
    )


def corrupt_bottom_truncation(image: Image.Image) -> Image.Image:
    array = np.array(image)
    height, width = array.shape[:2]

    start = random.randint(int(height * 0.55), int(height * 0.82))
    color = random.choice(
        [
            [0, 0, 0],
            [255, 255, 255],
            [0, 180, 0],
            [180, 0, 180],
            [128, 128, 128],
        ]
    )

    array[start:, :] = np.array(color, dtype=np.uint8)

    return Image.fromarray(array)


def corrupt_top_truncation(image: Image.Image) -> Image.Image:
    array = np.array(image)
    height, _ = array.shape[:2]

    end = random.randint(int(height * 0.18), int(height * 0.42))
    color = random.choice(
        [
            [0, 0, 0],
            [255, 255, 255],
            [0, 150, 0],
            [160, 0, 160],
        ]
    )

    array[:end, :] = np.array(color, dtype=np.uint8)

    return Image.fromarray(array)


def corrupt_left_panel(image: Image.Image) -> Image.Image:
    array = np.array(image)
    _, width = array.shape[:2]

    end = random.randint(int(width * 0.22), int(width * 0.48))
    color = random.choice(
        [
            [0, 0, 0],
            [255, 255, 255],
            [20, 180, 20],
            [180, 20, 180],
            [20, 20, 180],
        ]
    )

    array[:, :end] = np.array(color, dtype=np.uint8)

    return Image.fromarray(array)


def corrupt_right_panel(image: Image.Image) -> Image.Image:
    array = np.array(image)
    _, width = array.shape[:2]

    start = random.randint(int(width * 0.52), int(width * 0.78))
    color = random.choice(
        [
            [0, 0, 0],
            [255, 255, 255],
            [20, 180, 20],
            [180, 20, 180],
            [20, 20, 180],
        ]
    )

    array[:, start:] = np.array(color, dtype=np.uint8)

    return Image.fromarray(array)


def corrupt_random_color_blocks(image: Image.Image) -> Image.Image:
    array = np.array(image)
    height, width = array.shape[:2]

    block_count = random.randint(6, 18)

    for _ in range(block_count):
        block_width = random.randint(max(8, width // 18), max(12, width // 5))
        block_height = random.randint(max(8, height // 18), max(12, height // 5))

        x = random.randint(0, max(0, width - block_width))
        y = random.randint(0, max(0, height - block_height))

        color = np.random.randint(0, 256, size=(3,), dtype=np.uint8)
        array[y : y + block_height, x : x + block_width] = color

    return Image.fromarray(array)


def corrupt_horizontal_bands(image: Image.Image) -> Image.Image:
    array = np.array(image)
    height, width = array.shape[:2]

    band_count = random.randint(3, 8)

    for _ in range(band_count):
        y = random.randint(0, height - 1)
        band_height = random.randint(max(2, height // 80), max(4, height // 18))
        color = np.random.randint(0, 256, size=(3,), dtype=np.uint8)

        array[y : min(height, y + band_height), :] = color

    return Image.fromarray(array)


def corrupt_vertical_bands(image: Image.Image) -> Image.Image:
    array = np.array(image)
    height, width = array.shape[:2]

    band_count = random.randint(3, 8)

    for _ in range(band_count):
        x = random.randint(0, width - 1)
        band_width = random.randint(max(2, width // 80), max(4, width // 18))
        color = np.random.randint(0, 256, size=(3,), dtype=np.uint8)

        array[:, x : min(width, x + band_width)] = color

    return Image.fromarray(array)


def corrupt_channel_shift(image: Image.Image) -> Image.Image:
    array = np.array(image)

    shift_x = random.randint(8, 35)
    shift_y = random.randint(4, 25)

    shifted = array.copy()
    shifted[:, :, 0] = np.roll(array[:, :, 0], shift=shift_x, axis=1)
    shifted[:, :, 2] = np.roll(array[:, :, 2], shift=shift_y, axis=0)

    return Image.fromarray(shifted)


def corrupt_missing_color_channel(image: Image.Image) -> Image.Image:
    array = np.array(image)

    channel = random.choice([0, 1, 2])
    mode = random.choice(["zero", "max", "mean"])

    if mode == "zero":
        array[:, :, channel] = 0
    elif mode == "max":
        array[:, :, channel] = 255
    else:
        array[:, :, channel] = int(np.mean(array[:, :, channel]))

    return Image.fromarray(array)


def corrupt_hot_pixels(image: Image.Image) -> Image.Image:
    array = np.array(image)
    height, width = array.shape[:2]

    pixel_count = int(height * width * random.uniform(0.01, 0.06))

    ys = np.random.randint(0, height, size=pixel_count)
    xs = np.random.randint(0, width, size=pixel_count)

    colors = np.random.randint(0, 256, size=(pixel_count, 3), dtype=np.uint8)
    array[ys, xs] = colors

    return Image.fromarray(array)


def corrupt_jpeg_degradation(image: Image.Image) -> Image.Image:
    temp_array = np.array(image)
    encode_quality = random.randint(3, 14)

    success, encoded = cv2.imencode(
        ".jpg",
        cv2.cvtColor(temp_array, cv2.COLOR_RGB2BGR),
        [int(cv2.IMWRITE_JPEG_QUALITY), encode_quality],
    )

    if not success:
        return image

    decoded = cv2.imdecode(encoded, cv2.IMREAD_COLOR)

    if decoded is None:
        return image

    decoded_rgb = cv2.cvtColor(decoded, cv2.COLOR_BGR2RGB)

    return Image.fromarray(decoded_rgb)


def corrupt_partial_gray_panel(image: Image.Image) -> Image.Image:
    array = np.array(image)
    height, width = array.shape[:2]

    y_start = random.randint(0, int(height * 0.55))
    y_end = random.randint(int(height * 0.45), height)

    if y_end <= y_start:
        y_end = min(height, y_start + max(10, height // 4))

    gray_value = random.randint(80, 180)
    array[y_start:y_end, :] = [gray_value, gray_value, gray_value]

    return Image.fromarray(array)


def corrupt_green_or_magenta_panel(image: Image.Image) -> Image.Image:
    array = np.array(image)
    height, width = array.shape[:2]

    orientation = random.choice(["horizontal", "vertical"])
    color = random.choice(
        [
            [0, 255, 0],
            [255, 0, 255],
            [0, 180, 80],
            [160, 0, 220],
        ]
    )

    if orientation == "horizontal":
        start = random.randint(int(height * 0.35), int(height * 0.75))
        array[start:, :] = np.array(color, dtype=np.uint8)
    else:
        start = random.randint(int(width * 0.35), int(width * 0.75))
        array[:, start:] = np.array(color, dtype=np.uint8)

    return Image.fromarray(array)


def corrupt_block_shuffle(image: Image.Image) -> Image.Image:
    array = np.array(image)
    height, width = array.shape[:2]

    grid_size = random.choice([4, 5, 6])
    block_h = height // grid_size
    block_w = width // grid_size

    blocks = []

    for row in range(grid_size):
        for col in range(grid_size):
            y1 = row * block_h
            y2 = height if row == grid_size - 1 else (row + 1) * block_h
            x1 = col * block_w
            x2 = width if col == grid_size - 1 else (col + 1) * block_w

            blocks.append(array[y1:y2, x1:x2].copy())

    random.shuffle(blocks)

    output = array.copy()
    block_index = 0

    for row in range(grid_size):
        for col in range(grid_size):
            y1 = row * block_h
            y2 = height if row == grid_size - 1 else (row + 1) * block_h
            x1 = col * block_w
            x2 = width if col == grid_size - 1 else (col + 1) * block_w

            block = cv2.resize(blocks[block_index], (x2 - x1, y2 - y1))
            output[y1:y2, x1:x2] = block
            block_index += 1

    return Image.fromarray(output)


if __name__ == "__main__":
    main()