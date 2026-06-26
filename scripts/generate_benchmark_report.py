"""Generate benchmark report artifacts from committed metric JSON files."""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "docs" / "assets" / "benchmarks" / "smoke-demo-metrics.json"
DEFAULT_REPORT = ROOT / "docs" / "assets" / "benchmarks" / "smoke-demo-report.md"
DEFAULT_CHART = ROOT / "docs" / "assets" / "benchmarks" / "smoke-demo-chart.svg"


DISPLAY_NAMES = {
    "processing_success_rate": "Processing success",
    "bbox_validity_rate": "BBox validity",
    "feishu_alert_success_rate": "Feishu alert success",
    "total_videos": "Total videos",
    "high_risk_alerts": "High-risk alerts",
    "human_review_required": "Human review required",
    "remediation_tickets_created_by_default": "Tickets by default",
    "post_remediation_verifications_by_default": "Verifications by default",
}


def load_metrics(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def format_metric(key: str, value: Any) -> str:
    if key.endswith("_rate") and isinstance(value, (int, float)):
        return f"{value * 100:.0f}%"
    return str(value)


def metric_rows(metrics: dict[str, Any]) -> list[tuple[str, Any]]:
    preferred = [
        "total_videos",
        "processing_success_rate",
        "bbox_validity_rate",
        "high_risk_alerts",
        "feishu_alert_success_rate",
        "human_review_required",
        "remediation_tickets_created_by_default",
        "post_remediation_verifications_by_default",
    ]
    return [(key, metrics[key]) for key in preferred if key in metrics]


def generate_report(data: dict[str, Any], chart_path: Path) -> str:
    metrics = data.get("metrics", {})
    rows = "\n".join(
        f"| {DISPLAY_NAMES.get(key, key)} | `{key}` | {format_metric(key, value)} |"
        for key, value in metric_rows(metrics)
    )
    artifacts = "\n".join(f"- `{item}`" for item in data.get("expected_artifacts", []))
    notes = "\n".join(f"- {item}" for item in data.get("notes", []))
    rel_chart = chart_path.name
    return f"""# Smoke Demo Benchmark Report

This report is generated from
[`smoke-demo-metrics.json`](smoke-demo-metrics.json). It validates workflow
integrity for the deterministic seeded demo. It is not a model-quality benchmark.

![Smoke benchmark chart]({rel_chart})

## Summary

| Field | Value |
| --- | --- |
| Benchmark type | `{data.get("benchmark_type", "")}` |
| Scope | `{data.get("scope", "")}` |
| Dataset | `{data.get("dataset", "")}` |
| Model | `{data.get("model", "")}` |

## Metrics

| Metric | Key | Value |
| --- | --- | --- |
{rows}

## Expected Artifacts

{artifacts}

## Notes

{notes}
"""


def bar(width: float, maximum: float = 1.0) -> int:
    if maximum <= 0:
        return 0
    return int(max(0, min(1, width / maximum)) * 360)


def generate_chart(data: dict[str, Any]) -> str:
    metrics = data.get("metrics", {})
    chart_items = [
        ("Processing success", float(metrics.get("processing_success_rate", 0)), "rate"),
        ("BBox validity", float(metrics.get("bbox_validity_rate", 0)), "rate"),
        ("Feishu alert success", float(metrics.get("feishu_alert_success_rate", 0)), "rate"),
        ("High-risk alerts", float(metrics.get("high_risk_alerts", 0)), "count"),
    ]
    width = 760
    row_h = 54
    top = 72
    height = top + row_h * len(chart_items) + 36
    rows: list[str] = []
    for index, (label, value, kind) in enumerate(chart_items):
        y = top + index * row_h
        max_value = 1.0 if kind == "rate" else max(1.0, value)
        bar_w = bar(value, max_value)
        shown = f"{value * 100:.0f}%" if kind == "rate" else str(int(value))
        rows.append(
            f'<text x="32" y="{y + 21}" class="label">{label}</text>'
            f'<rect x="260" y="{y}" width="360" height="24" rx="4" class="track"/>'
            f'<rect x="260" y="{y}" width="{bar_w}" height="24" rx="4" class="bar"/>'
            f'<text x="640" y="{y + 19}" class="value">{shown}</text>'
        )
    body = "\n  ".join(rows)
    return f"""<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}" role="img" aria-labelledby="title desc">
  <title id="title">Industrial Video Safety Agent smoke benchmark</title>
  <desc id="desc">Smoke benchmark metrics for deterministic seeded demo.</desc>
  <style>
    .bg {{ fill: #ffffff; }}
    .title {{ font: 700 22px Arial, sans-serif; fill: #111827; }}
    .subtitle {{ font: 14px Arial, sans-serif; fill: #667085; }}
    .label {{ font: 14px Arial, sans-serif; fill: #1f2937; }}
    .value {{ font: 700 14px Arial, sans-serif; fill: #111827; }}
    .track {{ fill: #e5e7eb; }}
    .bar {{ fill: #1677ff; }}
  </style>
  <rect class="bg" width="{width}" height="{height}" rx="8"/>
  <text x="32" y="34" class="title">Smoke Demo Benchmark</text>
  <text x="32" y="56" class="subtitle">Workflow integrity metrics generated from committed JSON artifact.</text>
  {body}
</svg>
"""


def main() -> int:
    parser = argparse.ArgumentParser(description="Generate benchmark report and chart artifacts.")
    parser.add_argument("--input", default=str(DEFAULT_INPUT))
    parser.add_argument("--report", default=str(DEFAULT_REPORT))
    parser.add_argument("--chart", default=str(DEFAULT_CHART))
    args = parser.parse_args()

    input_path = Path(args.input)
    report_path = Path(args.report)
    chart_path = Path(args.chart)
    data = load_metrics(input_path)
    chart_path.write_text(generate_chart(data), encoding="utf-8")
    report_path.write_text(generate_report(data, chart_path), encoding="utf-8")
    print(f"Wrote {report_path.relative_to(ROOT)}")
    print(f"Wrote {chart_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
