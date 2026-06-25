"""Fine-tune an R3D-18 safety classifier on local safety behaviour videos."""

from __future__ import annotations

import argparse
import random
import subprocess
import tempfile
from pathlib import Path

import torch
from PIL import Image
from torch import nn
from torch.utils.data import DataLoader, Dataset, random_split
from torchvision.models.video import R3D_18_Weights, r3d_18
from torchvision.transforms import v2


LABELS = [
    "safe_walkway",
    "authorized_intervention",
    "closed_panel_cover",
    "safe_carrying",
    "walkway_violation",
    "unauthorized_intervention",
    "opened_panel_cover",
    "forklift_overload",
]
ALIASES = {
    "safe_walkway": ["safe_walkway", "safe-walkway", "safe walking", "safe"],
    "authorized_intervention": ["authorized_intervention", "authorized-intervention", "authorized"],
    "closed_panel_cover": ["closed_panel_cover", "closed-panel-cover", "closed cover", "closed_panel"],
    "safe_carrying": ["safe_carrying", "safe-carrying", "safe carrying"],
    "walkway_violation": ["walkway_violation", "walkway-violation", "violation", "unsafe_walkway"],
    "unauthorized_intervention": ["unauthorized_intervention", "unauthorized-intervention", "unauthorized", "unsafe intervention"],
    "opened_panel_cover": ["opened_panel_cover", "opened-panel-cover", "open cover", "opened_panel", "open_panel"],
    "forklift_overload": ["forklift_overload", "forklift-overload", "overload", "forklift"],
}
VIDEO_SUFFIXES = {".mp4", ".mov", ".avi", ".mkv", ".webm"}


def infer_label(path: Path) -> str | None:
    text = str(path).lower().replace("_", " ").replace("-", " ")
    for label, aliases in ALIASES.items():
        for alias in aliases:
            normalized = alias.lower().replace("_", " ").replace("-", " ")
            if normalized in text:
                return label
    return None


def discover_videos(root: Path, max_samples: int | None) -> list[tuple[Path, int]]:
    rows: list[tuple[Path, int]] = []
    for path in root.rglob("*"):
        if path.suffix.lower() not in VIDEO_SUFFIXES:
            continue
        label = infer_label(path)
        if label is None:
            continue
        rows.append((path, LABELS.index(label)))
    random.shuffle(rows)
    if max_samples:
        rows = rows[:max_samples]
    if not rows:
        raise SystemExit("No labelled videos found. Put videos under label folders or include label names in filenames.")
    return rows


def extract_frames(video: Path, count: int = 16) -> list[Image.Image]:
    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "frame_%03d.jpg"
        command = ["ffmpeg", "-y", "-i", str(video), "-vf", f"fps=8,scale=171:128", "-frames:v", str(count), str(output)]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        paths = sorted(Path(tmp).glob("frame_*.jpg"))
        if not paths:
            raise RuntimeError(f"No frames extracted from {video}")
        while len(paths) < count:
            paths.append(paths[-1])
        return [Image.open(path).convert("RGB").copy() for path in paths[:count]]


class SafetyVideoDataset(Dataset):
    def __init__(self, rows: list[tuple[Path, int]]) -> None:
        self.rows = rows
        self.transform = v2.Compose([
            v2.Resize((128, 171)),
            v2.CenterCrop((112, 112)),
            v2.ToImage(),
            v2.ToDtype(torch.float32, scale=True),
            v2.Normalize(mean=[0.43216, 0.394666, 0.37645], std=[0.22803, 0.22145, 0.216989]),
        ])

    def __len__(self) -> int:
        return len(self.rows)

    def __getitem__(self, index: int):
        path, label = self.rows[index]
        frames = extract_frames(path)
        tensor = torch.stack([self.transform(frame) for frame in frames], dim=1)
        return tensor, torch.tensor(label, dtype=torch.long)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/safe_unsafe_behaviours")
    parser.add_argument("--output", default="models/safety_r3d18.pt")
    parser.add_argument("--epochs", type=int, default=3)
    parser.add_argument("--batch-size", type=int, default=2)
    parser.add_argument("--lr", type=float, default=1e-4)
    parser.add_argument("--max-samples", type=int, default=0)
    args = parser.parse_args()

    root = Path(args.data_dir)
    rows = discover_videos(root, args.max_samples or None)
    train_size = max(1, int(len(rows) * 0.8))
    val_size = max(0, len(rows) - train_size)
    dataset = SafetyVideoDataset(rows)
    train_ds, val_ds = random_split(dataset, [train_size, val_size], generator=torch.Generator().manual_seed(42))
    train_loader = DataLoader(train_ds, batch_size=args.batch_size, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=args.batch_size, num_workers=0) if val_size else None

    device = "cuda" if torch.cuda.is_available() else "cpu"
    model = r3d_18(weights=R3D_18_Weights.KINETICS400_V1)
    model.fc = nn.Linear(model.fc.in_features, len(LABELS))
    model.to(device)

    optimizer = torch.optim.AdamW(model.parameters(), lr=args.lr)
    criterion = nn.CrossEntropyLoss()
    for epoch in range(args.epochs):
        model.train()
        total_loss = 0.0
        for videos, labels in train_loader:
            videos, labels = videos.to(device), labels.to(device)
            optimizer.zero_grad()
            loss = criterion(model(videos), labels)
            loss.backward()
            optimizer.step()
            total_loss += float(loss)
        accuracy = 0.0
        if val_loader:
            model.eval()
            correct = 0
            seen = 0
            with torch.no_grad():
                for videos, labels in val_loader:
                    videos, labels = videos.to(device), labels.to(device)
                    pred = model(videos).argmax(dim=1)
                    correct += int((pred == labels).sum())
                    seen += int(labels.numel())
            accuracy = correct / seen if seen else 0.0
        print(f"epoch={epoch + 1} loss={total_loss:.4f} val_accuracy={accuracy:.3f}")

    output = Path(args.output)
    output.parent.mkdir(parents=True, exist_ok=True)
    torch.save({"labels": LABELS, "model_state": model.state_dict(), "model_version": "safety-r3d18-v1"}, output)
    print(f"Saved model to: {output}")


if __name__ == "__main__":
    main()
