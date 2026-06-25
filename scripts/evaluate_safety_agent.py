"""Evaluate the safety classifier or the deployed video audit API on sample videos."""

from __future__ import annotations

import argparse
import json
import subprocess
import tempfile
import time
from pathlib import Path

import httpx

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
    candidates = [path.parent.name, path.stem]
    for candidate in candidates:
        text = candidate.lower().replace("_", " ").replace("-", " ")
        for label in sorted(LABELS, key=len, reverse=True):
            if text == label.replace("_", " "):
                return label
        for label in sorted(LABELS, key=len, reverse=True):
            if label.replace("_", " ") in text:
                return label
    text = path.stem.lower().replace("_", " ").replace("-", " ")
    for label, aliases in sorted(ALIASES.items(), key=lambda item: len(item[0]), reverse=True):
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
    rows = sorted(rows)
    if max_samples:
        rows = rows[:max_samples]
    if not rows:
        raise SystemExit("No labelled videos found.")
    return rows


def is_unsafe(label_index: int) -> bool:
    return LABELS[label_index] not in {"safe_walkway", "authorized_intervention", "closed_panel_cover", "safe_carrying"}


def is_high_or_critical(label_index: int) -> bool:
    return LABELS[label_index] in {"walkway_violation", "unauthorized_intervention", "opened_panel_cover", "forklift_overload"}


def risk_label_from_findings(findings: list[dict]) -> str:
    if not findings:
        return "safe_walkway"
    ordered = sorted(findings, key=lambda item: (float(item.get("confidence", 0)), int(item.get("end_ms", 0)) - int(item.get("start_ms", 0))), reverse=True)
    return str(ordered[0].get("label") or "safe_walkway")


def evaluate_api(args, rows: list[tuple[Path, int]]) -> None:
    client = httpx.Client(base_url=args.api_base, timeout=120)
    login = client.post("/api/auth/login", json={"username": args.username, "password": args.password})
    login.raise_for_status()
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}
    cases = []
    for path, label_index in rows:
        started = time.perf_counter()
        with path.open("rb") as handle:
            upload = client.post("/api/video-audits", headers=headers, files={"file": (path.name, handle, "video/mp4")})
        upload.raise_for_status()
        audit_id = upload.json()["id"]
        deadline = time.time() + args.timeout
        detail = None
        while time.time() < deadline:
            resp = client.get(f"/api/video-audits/{audit_id}", headers=headers)
            resp.raise_for_status()
            detail = resp.json()
            if detail["audit"]["status"] in {"completed", "needs_review", "failed"}:
                break
            time.sleep(2)
        predicted_label = risk_label_from_findings(detail.get("findings", []) if detail else [])
        predicted_index = LABELS.index(predicted_label) if predicted_label in LABELS else 0
        predicted_unsafe = bool(detail and detail["audit"]["risk_level"] in {"high", "critical", "needs_review"})
        cases.append({
            "file": str(path),
            "expected_label": LABELS[label_index],
            "predicted_label": predicted_label,
            "expected_unsafe": is_unsafe(label_index),
            "predicted_unsafe": predicted_unsafe,
            "expected_high_or_critical": is_high_or_critical(label_index),
            "predicted_high_or_critical": is_high_or_critical(predicted_index),
            "audit_id": audit_id,
            "status": detail["audit"]["status"] if detail else "timeout",
            "processing_seconds": round(time.perf_counter() - started, 3),
        })
    print_metrics(cases)


def evaluate_filenames(rows: list[tuple[Path, int]]) -> None:
    cases = []
    for path, label_index in rows:
        lower = path.name.lower()
        predicted_unsafe = any(token in lower for token in ["unsafe", "violation", "unauthorized", "open", "overload", "forklift"])
        predicted_label = "safe_walkway"
        for label in LABELS:
            if label.replace("_", " ") in lower.replace("_", " ").replace("-", " "):
                predicted_label = label
                break
        predicted_index = LABELS.index(predicted_label)
        cases.append({
            "file": str(path),
            "expected_label": LABELS[label_index],
            "predicted_label": predicted_label,
            "expected_unsafe": is_unsafe(label_index),
            "predicted_unsafe": predicted_unsafe,
            "expected_high_or_critical": is_high_or_critical(label_index),
            "predicted_high_or_critical": is_high_or_critical(predicted_index),
            "status": "filename-baseline",
            "processing_seconds": 0,
        })
    print_metrics(cases)


def extract_frames(video: Path, count: int = 16):
    from PIL import Image

    with tempfile.TemporaryDirectory() as tmp:
        output = Path(tmp) / "frame_%03d.jpg"
        command = ["ffmpeg", "-y", "-i", str(video), "-vf", "fps=8,scale=171:128", "-frames:v", str(count), str(output)]
        result = subprocess.run(command, capture_output=True, text=True, check=False)
        if result.returncode != 0:
            raise RuntimeError(result.stderr)
        paths = sorted(Path(tmp).glob("frame_*.jpg"))
        if not paths:
            raise RuntimeError(f"No frames extracted from {video}")
        while len(paths) < count:
            paths.append(paths[-1])
        return [Image.open(path).convert("RGB").copy() for path in paths[:count]]


def evaluate_model(args, rows: list[tuple[Path, int]]) -> None:
    import torch
    from torchvision.models.video import r3d_18
    from torchvision.transforms import v2

    device = "cuda" if torch.cuda.is_available() else "cpu"
    checkpoint = torch.load(args.model_path, map_location=device)
    labels = checkpoint.get("labels", LABELS)
    model = r3d_18(weights=None, num_classes=len(labels))
    model.load_state_dict(checkpoint["model_state"])
    model.to(device)
    model.eval()
    transform = v2.Compose([
        v2.Resize((128, 171)),
        v2.CenterCrop((112, 112)),
        v2.ToImage(),
        v2.ToDtype(torch.float32, scale=True),
        v2.Normalize(mean=[0.43216, 0.394666, 0.37645], std=[0.22803, 0.22145, 0.216989]),
    ])
    cases = []
    for path, label_index in rows:
        started = time.perf_counter()
        frames = extract_frames(path)
        tensor = torch.stack([transform(frame) for frame in frames], dim=1).unsqueeze(0).to(device)
        with torch.no_grad():
            probs = torch.softmax(model(tensor), dim=1)[0]
        predicted_index = int(torch.argmax(probs).item())
        predicted_label = labels[predicted_index]
        expected_label = LABELS[label_index]
        expected_index = labels.index(expected_label) if expected_label in labels else label_index
        cases.append({
            "file": str(path),
            "expected_label": expected_label,
            "predicted_label": predicted_label,
            "expected_unsafe": is_unsafe(label_index),
            "predicted_unsafe": predicted_label not in {"safe_walkway", "authorized_intervention", "closed_panel_cover", "safe_carrying"},
            "expected_high_or_critical": is_high_or_critical(label_index),
            "predicted_high_or_critical": predicted_label in {"walkway_violation", "unauthorized_intervention", "opened_panel_cover", "forklift_overload"},
            "confidence": round(float(probs[predicted_index]), 4),
            "status": "model",
            "processing_seconds": round(time.perf_counter() - started, 3),
            "expected_index": expected_index,
            "predicted_index": predicted_index,
        })
    print_metrics(cases)


def print_metrics(cases: list[dict]) -> None:
    tp = sum(1 for item in cases if item["expected_unsafe"] and item["predicted_unsafe"])
    fp = sum(1 for item in cases if not item["expected_unsafe"] and item["predicted_unsafe"])
    tn = sum(1 for item in cases if not item["expected_unsafe"] and not item["predicted_unsafe"])
    fn = sum(1 for item in cases if item["expected_unsafe"] and not item["predicted_unsafe"])
    accuracy = (tp + tn) / len(cases) if cases else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    precision = tp / (tp + fp) if (tp + fp) else 0
    class_correct = sum(1 for item in cases if item.get("expected_label") == item.get("predicted_label"))
    high_expected = sum(1 for item in cases if item.get("expected_high_or_critical"))
    high_recalled = sum(1 for item in cases if item.get("expected_high_or_critical") and item.get("predicted_high_or_critical"))
    successful = sum(1 for item in cases if item.get("status") not in {"failed", "timeout"})
    matrix = {label: {inner: 0 for inner in LABELS} for label in LABELS}
    for item in cases:
        expected = item.get("expected_label")
        predicted = item.get("predicted_label")
        if expected in matrix and predicted in matrix[expected]:
            matrix[expected][predicted] += 1
    processing_times = [float(item.get("processing_seconds", 0)) for item in cases]
    report = {
        "cases": len(cases),
        "binary_unsafe_accuracy": round(accuracy, 3),
        "class_accuracy": round(class_correct / len(cases), 3) if cases else 0,
        "unsafe_precision": round(precision, 3),
        "unsafe_recall": round(recall, 3),
        "high_critical_recall": round(high_recalled / high_expected, 3) if high_expected else 0,
        "end_to_end_success_rate": round(successful / len(cases), 3) if cases else 0,
        "avg_processing_seconds": round(sum(processing_times) / len(processing_times), 3) if processing_times else 0,
        "binary_confusion": {"tp": tp, "fp": fp, "tn": tn, "fn": fn},
        "class_confusion_matrix": matrix,
        "samples": cases,
    }
    print(json.dumps(report, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--data-dir", default="data/safe_unsafe_behaviours")
    parser.add_argument("--max-samples", type=int, default=24)
    parser.add_argument("--mode", choices=["api", "model", "filename-baseline"], default="filename-baseline")
    parser.add_argument("--model-path", default="models/safety_r3d18.pt")
    parser.add_argument("--api-base", default="http://localhost:8000")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="Admin123!")
    parser.add_argument("--timeout", type=int, default=180)
    args = parser.parse_args()

    rows = discover_videos(Path(args.data_dir), args.max_samples)
    if args.mode == "api":
        evaluate_api(args, rows)
    elif args.mode == "model":
        evaluate_model(args, rows)
    else:
        evaluate_filenames(rows)


if __name__ == "__main__":
    main()
