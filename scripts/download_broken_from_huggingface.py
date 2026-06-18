from pathlib import Path
from typing import Any

from datasets import load_dataset
from PIL import Image


DATASET_NAME = "MarMaster/corruption-gaussian_noise"
OUTPUT_DIR = Path("training_data/broken")
MAX_IMAGES = 1000


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    dataset = load_dataset(DATASET_NAME, split="train", streaming=True)

    saved_count = 0

    for row in dataset:
        if saved_count >= MAX_IMAGES:
            break

        image = extract_image(row)

        if image is None:
            continue

        image = image.convert("RGB")

        output_path = OUTPUT_DIR / f"huggingface_broken_{saved_count:05d}.jpg"
        image.save(output_path, format="JPEG", quality=95)

        saved_count += 1

        if saved_count % 50 == 0:
            print(f"Saved {saved_count} images...")

    print(f"Done. Saved {saved_count} images to {OUTPUT_DIR}")


def extract_image(row: dict[str, Any]) -> Image.Image | None:
    for value in row.values():
        if isinstance(value, Image.Image):
            return value

    return None


if __name__ == "__main__":
    main()