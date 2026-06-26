"""Render public dataset benchmark JSON into Markdown and SVG artifacts."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "docs" / "assets" / "benchmarks" / "public-24-one-frame.json"
DEFAULT_REPORT = ROOT / "docs" / "assets" / "benchmarks" / "public-24-one-frame-report.md"
DEFAULT_CHART = ROOT / "docs" / "assets" / "benchmarks" / "public-24-one-frame-chart.svg"


METRIC_NAMES = {
    "binary_unsafe_accuracy": "Binary unsafe accuracy",
    "class_accuracy": "8-class accuracy",
    "unsafe_precision": "Unsafe precision",
    "unsafe_recall": "Unsafe recall",
    "high_critical_recall": "High / critical recall",
    "end_to_end_success_rate": "End-to-end success",
    "avg_processing_seconds": "Avg processing seconds",
}


def load_json(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def display_path(path: Path) -> str:
    try:
        return str(path.resolve().relative_to(ROOT))
    except ValueError:
        return str(path)


def pct(value: Any) -> str:
    if isinstance(value, (int, float)):
        return f"{value * 100:.1f}%"
    return str(value)


def scalar(value: Any) -> str:
    if isinstance(value, float):
        return f"{value:.3f}".rstrip("0").rstrip(".")
    return str(value)


def sample_name(sample: dict[str, Any]) -> str:
    return Path(str(sample.get("file", ""))).name


def failure_cases(data: dict[str, Any]) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    samples = data.get("samples", [])
    false_positive = [
        item
        for item in samples
        if not item.get("expected_unsafe") and item.get("predicted_unsafe")
    ]
    false_negative = [
        item
        for item in samples
        if item.get("expected_unsafe") and not item.get("predicted_unsafe")
    ]
    return false_positive, false_negative


def generate_report(data: dict[str, Any], input_path: Path, chart_path: Path) -> str:
    metric_keys = [
        "binary_unsafe_accuracy",
        "class_accuracy",
        "unsafe_precision",
        "unsafe_recall",
        "high_critical_recall",
        "end_to_end_success_rate",
        "avg_processing_seconds",
    ]
    rows = []
    for key in metric_keys:
        value = data.get(key, "")
        shown = pct(value) if key != "avg_processing_seconds" else f"{scalar(value)}s"
        rows.append(f"| {METRIC_NAMES[key]} | `{key}` | {shown} |")

    fp, fn = failure_cases(data)
    fp_rows = "\n".join(
        f"- `{sample_name(item)}` expected `{item.get('expected_label')}`, predicted `{item.get('predicted_label')}`"
        for item in fp[:8]
    ) or "- None in this run."
    fn_rows = "\n".join(
        f"- `{sample_name(item)}` expected `{item.get('expected_label')}`, predicted `{item.get('predicted_label')}`"
        for item in fn[:8]
    ) or "- None in this run."
    sample_rows = "\n".join(
        "| `{}` | `{}` | `{}` | `{}` | {}s |".format(
            sample_name(item),
            item.get("expected_label", ""),
            item.get("predicted_label", ""),
            item.get("status", ""),
            scalar(item.get("processing_seconds", 0)),
        )
        for item in data.get("samples", [])[:24]
    )
    rel_chart = chart_path.name
    return f"""# Public Safety Video Benchmark

This report is generated from [`{input_path.name}`]({input_path.name}).
It evaluates the deployed API workflow on public safety video samples.

![Public benchmark chart]({rel_chart})

## Run Configuration

| Field | Value |
| --- | --- |
| Benchmark type | `{data.get("benchmark_type", "")}` |
| Generated at | `{data.get("generated_at", "")}` |
| Mode | `{data.get("mode", "")}` |
| Data dir | `{data.get("data_dir", "")}` |
| Samples | `{data.get("cases", "")}` |
| Max samples | `{data.get("max_samples", "")}` |
| VLM frame budget | `{data.get("vision_max_frames", "")}` |

## Metrics

| Metric | Key | Value |
| --- | --- | --- |
{chr(10).join(rows)}

## Binary Confusion

| TP | FP | TN | FN |
| ---: | ---: | ---: | ---: |
| {data.get("binary_confusion", {}).get("tp", 0)} | {data.get("binary_confusion", {}).get("fp", 0)} | {data.get("binary_confusion", {}).get("tn", 0)} | {data.get("binary_confusion", {}).get("fn", 0)} |

## False Positives

{fp_rows}

## False Negatives

{fn_rows}

## Sample Outputs

| File | Expected | Predicted | Status | Latency |
| --- | --- | --- | --- | ---: |
{sample_rows}

## Notes

- This benchmark uses a one-frame VLM budget by default to control cost.
- One-frame evaluation is intentionally low cost; increase `--vision-max-frames` for a higher-recall run.
- Model outputs are safety-assistant signals and require human review before operational decisions.
"""


def bar(value: float, max_value: float = 1.0) -> int:
    if max_value <= 0:
        return 0
    return int(max(0, min(1, value / max_value)) * 360)


def generate_chart(data: dict[str, Any]) -> str:
    chart_items = [
        ("Unsafe recall", float(data.get("unsafe_recall", 0)), "rate"),
        ("High / critical recall", float(data.get("high_critical_recall", 0)), "rate"),
        ("End-to-end success", float(data.get("end_to_end_success_rate", 0)), "rate"),
        ("Avg latency", float(data.get("avg_processing_seconds", 0)), "seconds"),
    ]
    width = 800
    row_h = 56
    top = 86
    height = top + row_h * len(chart_items) + 42
    max_seconds = max(1.0, float(data.get("avg_processing_seconds", 0)))
    rows = []
    for index, (label, value, kind) in enumerate(chart_items):
        y = top + index * row_h
        max_value = 1.0 if kind == "rate" else max_seconds
        shown = f"{value * 100:.1f}%" if kind == "rate" else f"{value:.1f}s"
        rows.append(
            f'<text x="32" y="{y + 21}" class="label">{label}</text>'
            f'<rect x="270" y="{y}" width="360" height="24" rx="4" class="track"/>'
            f'<rect x="270" y="{y}" width="{bar(value, max_value)}" height="24" rx="4" class="bar"/>'
            f'<text x="650" y="{y + 19}" class="value">{shown}</text>'
        )
    body = "\n  ".join(rows)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Public safety video benchmark</title>
  <desc id="desc">Benchmark metrics for public safety videos using the deployed API workflow.</desc>
  <style>
    .bg {{ fill: #ffffff; }}
    .title {{ font: 700 22px Arial, sans-serif; fill: #111827; }}
    .subtitle {{ font: 14px Arial, sans-serif; fill: #667085; }}
    .label {{ font: 14px Arial, sans-serif; fill: #1f2937; }}
    .value {{ font: 700 14px Arial, sans-serif; fill: #111827; }}
    .track {{ fill: #e5e7eb; }}
    .bar {{ fill: #2563eb; }}
  </style>
  <rect class="bg" width="{width}" height="{height}" rx="8"/>
  <text x="32" y="36" class="title">Public Safety Video Benchmark</text>
  <text x="32" y="60" class="subtitle">{data.get("cases", 0)} samples, VLM frame budget: {data.get("vision_max_frames", "")}</text>
  {body}
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Render public benchmark report and SVG chart.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--chart", default=str(DEFAULT_CHART))
    args = parser.parse_args()

    input_path = Path(args.input)
    report_path = Path(args.report)
    chart_path = Path(args.chart)
    data = load_json(input_path)
    report_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.parent.mkdir(parents=True, exist_ok=True)
    chart_path.write_text(generate_chart(data), encoding="utf-8")
    report_path.write_text(generate_report(data, input_path, chart_path), encoding="utf-8")
    print(f"Wrote {display_path(report_path)}")
    print(f"Wrote {display_path(chart_path)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
