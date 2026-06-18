from pathlib import Path

import torch
from PIL import Image, ImageFile, UnidentifiedImageError
from torch.utils.data import DataLoader, Dataset, random_split
from torchvision import models, transforms

ImageFile.LOAD_TRUNCATED_IMAGES = False


PROJECT_ROOT = Path(__file__).resolve().parent.parent
TRAINING_DATA_DIR = PROJECT_ROOT / "training_data"
MODEL_OUTPUT_PATH = PROJECT_ROOT / "models" / "image_corruption_classifier.pt"

CLASS_NAMES = ["ok", "broken"]
BATCH_SIZE = 16
EPOCHS = 8
LEARNING_RATE = 0.0003
VALIDATION_RATIO = 0.2
RANDOM_SEED = 42


class ImageCorruptionDataset(Dataset):
    def __init__(self, root_dir: Path, transform: transforms.Compose) -> None:
        self.root_dir = root_dir
        self.transform = transform
        self.samples: list[tuple[Path, int]] = []

        skipped_count = 0

        for label, class_name in enumerate(CLASS_NAMES):
            class_dir = root_dir / class_name

            if not class_dir.exists():
                raise FileNotFoundError(f"Missing training folder: {class_dir}")

            for path in class_dir.rglob("*"):
                if not path.is_file():
                    continue

                if path.suffix.lower() not in {".jpg", ".jpeg", ".png", ".webp", ".bmp"}:
                    continue

                if is_valid_training_image(path):
                    self.samples.append((path, label))
                else:
                    skipped_count += 1
                    print(f"Skipping invalid training image: {path}")

        if not self.samples:
            raise ValueError(f"No valid training images found in {root_dir}")

        print(f"Loaded {len(self.samples)} valid training images.")
        print(f"Skipped {skipped_count} invalid images.")

        self.print_class_counts()

    def __len__(self) -> int:
        return len(self.samples)

    def __getitem__(self, index: int) -> tuple[torch.Tensor, int]:
        path, label = self.samples[index]

        with Image.open(path) as image:
            image.load()
            image = image.convert("RGB")

        return self.transform(image), label

    def print_class_counts(self) -> None:
        counts = {class_name: 0 for class_name in CLASS_NAMES}

        for _, label in self.samples:
            counts[CLASS_NAMES[label]] += 1

        print("Class counts:")
        for class_name, count in counts.items():
            print(f"- {class_name}: {count}")


def is_valid_training_image(path: Path) -> bool:
    try:
        with Image.open(path) as image:
            image.verify()

        with Image.open(path) as image:
            image.load()
            image.convert("RGB")

        return True

    except (UnidentifiedImageError, OSError, ValueError):
        return False


def main() -> None:
    torch.manual_seed(RANDOM_SEED)

    MODEL_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)

    train_transform = transforms.Compose(
        [
            transforms.Resize((256, 256)),
            transforms.RandomResizedCrop(224, scale=(0.75, 1.0)),
            transforms.RandomHorizontalFlip(),
            transforms.ColorJitter(
                brightness=0.12,
                contrast=0.12,
                saturation=0.08,
                hue=0.02,
            ),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )

    validation_transform = transforms.Compose(
        [
            transforms.Resize((224, 224)),
            transforms.ToTensor(),
            transforms.Normalize(
                mean=[0.485, 0.456, 0.406],
                std=[0.229, 0.224, 0.225],
            ),
        ]
    )

    full_dataset = ImageCorruptionDataset(TRAINING_DATA_DIR, transform=train_transform)

    validation_size = max(1, int(len(full_dataset) * VALIDATION_RATIO))
    train_size = len(full_dataset) - validation_size

    if train_size <= 0:
        raise ValueError("Not enough valid images to split train and validation datasets.")

    train_dataset, validation_dataset = random_split(
        full_dataset,
        [train_size, validation_size],
        generator=torch.Generator().manual_seed(RANDOM_SEED),
    )

    validation_dataset.dataset.transform = validation_transform

    train_loader = DataLoader(train_dataset, batch_size=BATCH_SIZE, shuffle=True)
    validation_loader = DataLoader(validation_dataset, batch_size=BATCH_SIZE, shuffle=False)

    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    print(f"Using device: {device}")

    model = build_model()
    model.to(device)

    class_weights = calculate_class_weights(full_dataset).to(device)
    criterion = torch.nn.CrossEntropyLoss(weight=class_weights)
    optimizer = torch.optim.AdamW(model.parameters(), lr=LEARNING_RATE)

    best_validation_accuracy = 0.0

    for epoch in range(1, EPOCHS + 1):
        train_loss, train_accuracy = run_training_epoch(
            model=model,
            loader=train_loader,
            criterion=criterion,
            optimizer=optimizer,
            device=device,
        )

        validation_loss, validation_accuracy = run_validation_epoch(
            model=model,
            loader=validation_loader,
            criterion=criterion,
            device=device,
        )

        print(
            f"Epoch {epoch}/{EPOCHS} | "
            f"train loss {train_loss:.4f} | train acc {train_accuracy:.2%} | "
            f"val loss {validation_loss:.4f} | val acc {validation_accuracy:.2%}"
        )

        if validation_accuracy >= best_validation_accuracy:
            best_validation_accuracy = validation_accuracy
            save_model(model, best_validation_accuracy)

    print(f"Saved model to: {MODEL_OUTPUT_PATH}")
    print(f"Best validation accuracy: {best_validation_accuracy:.2%}")


def build_model() -> torch.nn.Module:
    weights = models.MobileNet_V3_Small_Weights.DEFAULT
    model = models.mobilenet_v3_small(weights=weights)

    for parameter in model.features.parameters():
        parameter.requires_grad = False

    input_features = model.classifier[3].in_features
    model.classifier[3] = torch.nn.Linear(input_features, len(CLASS_NAMES))

    return model


def calculate_class_weights(dataset: ImageCorruptionDataset) -> torch.Tensor:
    counts = [0 for _ in CLASS_NAMES]

    for _, label in dataset.samples:
        counts[label] += 1

    total = sum(counts)
    weights = [total / max(count, 1) for count in counts]

    return torch.tensor(weights, dtype=torch.float32)


def run_training_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    criterion: torch.nn.Module,
    optimizer: torch.optim.Optimizer,
    device: torch.device,
) -> tuple[float, float]:
    model.train()

    total_loss = 0.0
    correct = 0
    total = 0

    for images, labels in loader:
        images = images.to(device)
        labels = labels.to(device)

        optimizer.zero_grad()

        outputs = model(images)
        loss = criterion(outputs, labels)
        loss.backward()
        optimizer.step()

        total_loss += float(loss.item()) * images.size(0)
        predictions = torch.argmax(outputs, dim=1)

        correct += int((predictions == labels).sum().item())
        total += labels.size(0)

    return total_loss / max(total, 1), correct / max(total, 1)


def run_validation_epoch(
    model: torch.nn.Module,
    loader: DataLoader,
    criterion: torch.nn.Module,
    device: torch.device,
) -> tuple[float, float]:
    model.eval()

    total_loss = 0.0
    correct = 0
    total = 0

    with torch.no_grad():
        for images, labels in loader:
            images = images.to(device)
            labels = labels.to(device)

            outputs = model(images)
            loss = criterion(outputs, labels)

            total_loss += float(loss.item()) * images.size(0)
            predictions = torch.argmax(outputs, dim=1)

            correct += int((predictions == labels).sum().item())
            total += labels.size(0)

    return total_loss / max(total, 1), correct / max(total, 1)


def save_model(model: torch.nn.Module, validation_accuracy: float) -> None:
    torch.save(
        {
            "class_names": CLASS_NAMES,
            "validation_accuracy": validation_accuracy,
            "model_state_dict": model.state_dict(),
        },
        MODEL_OUTPUT_PATH,
    )


if __name__ == "__main__":
    main()