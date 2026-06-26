"""Validate the public VLM prompt and output schema contract."""

from __future__ import annotations

import json
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
PROMPT = ROOT / "prompts" / "safety_inspection_skill.md"
SCHEMA = ROOT / "prompts" / "safety_findings.schema.json"
WORKER = ROOT / "services" / "video-worker" / "app" / "main.py"
MCP_SERVER = ROOT / "services" / "safety-mcp-server" / "server.py"

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
RISK_LEVELS = ["critical", "high", "medium", "low", "needs_review"]
FIELDS = [
    "findings",
    "label",
    "risk_level",
    "confidence",
    "timestamp_ms",
    "start_ms",
    "end_ms",
    "bbox",
    "reason",
    "recommendation",
    "evidence_caption",
]
BOUNDARY_PHRASES = [
    "不确定就输出 `needs_review`",
    "不能直接判 `high`",
    "框住物料就描述物料风险",
    "所有面向用户的字段必须使用简体中文",
]


def fail(message: str) -> None:
    raise AssertionError(message)


def load_text(path: Path) -> str:
    if not path.exists():
        fail(f"missing file: {path.relative_to(ROOT)}")
    return path.read_text(encoding="utf-8")


def validate_prompt() -> None:
    text = load_text(PROMPT)
    for label in LABELS:
        if label not in text:
            fail(f"prompt is missing label: {label}")
    for level in RISK_LEVELS:
        if level not in text:
            fail(f"prompt is missing risk level: {level}")
    for field in FIELDS:
        if field not in text:
            fail(f"prompt is missing output field: {field}")
    for phrase in BOUNDARY_PHRASES:
        if phrase not in text:
            fail(f"prompt is missing boundary rule: {phrase}")


def validate_schema() -> None:
    schema = json.loads(load_text(SCHEMA))
    findings = schema["properties"]["findings"]["items"]
    required = set(findings["required"])
    if not set(FIELDS[1:]).issubset(required):
        fail("schema required fields do not match prompt contract")
    label_enum = set(findings["properties"]["label"]["enum"])
    if label_enum != set(LABELS):
        fail(f"schema label enum mismatch: {sorted(label_enum)}")
    risk_enum = set(findings["properties"]["risk_level"]["enum"])
    if risk_enum != set(RISK_LEVELS):
        fail(f"schema risk_level enum mismatch: {sorted(risk_enum)}")
    bbox = findings["properties"]["bbox"]
    if "oneOf" not in bbox:
        fail("bbox schema must allow normalized box or null")


def validate_code_uses_shared_prompt() -> None:
    worker = load_text(WORKER)
    mcp = load_text(MCP_SERVER)
    if "_safety_skill_candidates" not in worker or "prompts\" / \"safety_inspection_skill.md" not in worker:
        fail("video-worker must load the shared prompt from prompts/")
    if "PROMPT_CANDIDATES" not in mcp or "_load_safety_prompt" not in mcp:
        fail("MCP server must load the shared prompt from prompts/")


def main() -> int:
    try:
        validate_prompt()
        validate_schema()
        validate_code_uses_shared_prompt()
    except Exception as exc:
        print(f"Prompt contract check failed: {exc}", file=sys.stderr)
        return 1
    print("Prompt contract check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
