"""Download the public Safe and Unsafe Behaviours dataset from Hugging Face."""

from __future__ import annotations

import argparse
import json
import shutil
from collections import defaultdict
from pathlib import Path


LABEL_MAP = {
    "Safe Walkway Violation": "walkway_violation",
    "Unauthorized Intervention": "unauthorized_intervention",
    "Opened Panel Cover": "opened_panel_cover",
    "Carrying Overload with Forklift": "forklift_overload",
    "Safe Walkway": "safe_walkway",
    "Authorized Intervention": "authorized_intervention",
    "Closed Panel Cover": "closed_panel_cover",
    "Safe Carrying": "safe_carrying",
}


def _load_samples(repo: str):
    from huggingface_hub import hf_hub_download

    path = Path(hf_hub_download(repo, "samples.json", repo_type="dataset"))
    payload = json.loads(path.read_text(encoding="utf-8"))
    return payload.get("samples", [])


def _select_samples(samples: list[dict], max_per_class: int, split: str) -> list[dict]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for sample in samples:
        tags = set(sample.get("tags") or [])
        if split != "all" and split not in tags:
            continue
        label = sample.get("ground_truth", {}).get("label")
        if label in LABEL_MAP:
            grouped[LABEL_MAP[label]].append(sample)

    selected: list[dict] = []
    for label in sorted(grouped):
        rows = sorted(grouped[label], key=lambda item: int(item.get("metadata", {}).get("size_bytes") or 0))
        selected.extend(rows[:max_per_class])
    return selected


def _download_sample_subset(repo: str, output: Path, max_per_class: int, split: str) -> None:
    from huggingface_hub import hf_hub_download

    output.mkdir(parents=True, exist_ok=True)
    selected = _select_samples(_load_samples(repo), max_per_class, split)
    manifest = []
    for sample in selected:
        source_path = sample["filepath"]
        source_label = sample["ground_truth"]["label"]
        label = LABEL_MAP[source_label]
        cached = Path(hf_hub_download(repo, source_path, repo_type="dataset"))
        destination = output / label / f"{label}__{Path(source_path).name}"
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(cached, destination)
        manifest.append({
            "path": str(destination.relative_to(output)),
            "source_path": source_path,
            "source_label": source_label,
            "label": label,
            "split": sample.get("tags", []),
            "size_bytes": sample.get("metadata", {}).get("size_bytes"),
            "duration": sample.get("metadata", {}).get("duration"),
        })
        print(f"{label}: {source_path} -> {destination}")

    (output / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"Downloaded {len(manifest)} sample videos to: {output}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--repo", default="Voxel51/Safe_and_Unsafe_Behaviours")
    parser.add_argument("--output", default="data/safe_unsafe_behaviours")
    parser.add_argument("--max-per-class", type=int, default=0, help="Download a small labelled subset instead of the full snapshot.")
    parser.add_argument("--split", choices=["train", "test", "all"], default="test")
    args = parser.parse_args()

    try:
        from huggingface_hub import snapshot_download
    except ImportError as exc:
        raise SystemExit("Install huggingface_hub first: pip install huggingface_hub") from exc

    output = Path(args.output)
    output.mkdir(parents=True, exist_ok=True)
    if args.max_per_class > 0:
        _download_sample_subset(args.repo, output, args.max_per_class, args.split)
        return

    path = snapshot_download(repo_id=args.repo, repo_type="dataset", local_dir=str(output))
    print(f"Downloaded dataset to: {path}")


if __name__ == "__main__":
    main()
