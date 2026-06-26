"""Validate the safety Agent workflow spec against code and docs."""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path
from typing import Any


ROOT = Path(__file__).resolve().parents[1]
SPEC_PATH = ROOT / "config" / "safety_agent_workflow.json"
WORKER = ROOT / "services" / "video-worker" / "app" / "main.py"
TICKET_SERVICE = ROOT / "services" / "ticket-service" / "app" / "main.py"
API_SERVICE = ROOT / "services" / "video-audit-service" / "app" / "main.py"
README = ROOT / "README.md"
SEED = ROOT / "scripts" / "seed_demo_safety_agent.py"

REQUIRED_TOOLS = [
    "receive_task",
    "load_video",
    "sample_video_frames",
    "inspect_safety_frame",
    "validate_bbox",
    "merge_risk_events",
    "build_video_memory",
    "decide_safety_action",
    "write_audit_report",
    "send_feishu_alert",
    "recommend_remediation_ticket",
    "verify_remediation",
]
REQUIRED_STATUSES = {"running", "waiting_review", "waiting_remediation", "completed", "failed"}
REQUIRED_MCP_TOOLS = {"inspect_safety_frame", "query_video_memory", "send_feishu_alert"}


def fail(message: str) -> None:
    raise AssertionError(message)


def read_text(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def load_spec() -> dict[str, Any]:
    if not SPEC_PATH.exists():
        fail(f"Missing workflow spec: {SPEC_PATH.relative_to(ROOT)}")
    return json.loads(read_text(SPEC_PATH))


def validate_tools(spec: dict[str, Any]) -> list[str]:
    tools = spec.get("tools")
    if not isinstance(tools, list) or not tools:
        fail("workflow spec must contain a non-empty tools list")
    names = [item.get("name") for item in tools]
    if names != REQUIRED_TOOLS:
        fail(f"tool order mismatch: expected {REQUIRED_TOOLS}, got {names}")
    if len(names) != len(set(names)):
        fail("tool names must be unique")
    orders = [item.get("order") for item in tools]
    if orders != list(range(1, len(tools) + 1)):
        fail(f"tool order values must be contiguous from 1: {orders}")
    for item in tools:
        for key in ("kind", "stage", "why", "inputs", "outputs", "artifacts"):
            if key not in item:
                fail(f"tool {item.get('name')} is missing {key}")
        if not str(item["why"]).strip():
            fail(f"tool {item['name']} must explain why it exists")
    return names


def validate_transitions(spec: dict[str, Any], names: list[str]) -> None:
    transitions = spec.get("transitions")
    if not isinstance(transitions, list):
        fail("workflow spec must contain transitions")
    expected = list(zip(names, names[1:]))
    actual = [(item.get("from"), item.get("to")) for item in transitions]
    if actual != expected:
        fail(f"transition chain mismatch: expected {expected}, got {actual}")
    for item in transitions:
        if not item.get("condition"):
            fail(f"transition {item} is missing condition")


def validate_statuses(spec: dict[str, Any]) -> None:
    statuses = set(spec.get("run_statuses", []))
    if statuses != REQUIRED_STATUSES:
        fail(f"run statuses mismatch: expected {sorted(REQUIRED_STATUSES)}, got {sorted(statuses)}")
    pause_statuses = {item.get("status") for item in spec.get("pause_points", [])}
    if not {"waiting_review", "waiting_remediation"}.issubset(pause_statuses):
        fail("pause_points must include waiting_review and waiting_remediation")
    terminal_statuses = {item.get("status") for item in spec.get("terminal_states", [])}
    if not {"completed", "failed"}.issubset(terminal_statuses):
        fail("terminal_states must include completed and failed")


def validate_code_references(names: list[str]) -> None:
    worker_text = read_text(WORKER)
    ticket_text = read_text(TICKET_SERVICE)
    api_text = read_text(API_SERVICE)
    seed_text = read_text(SEED)
    for name in names:
        if name == "verify_remediation":
            if name not in ticket_text:
                fail("verify_remediation must be implemented in ticket-service")
        elif name == "query_video_memory":
            if name not in api_text:
                fail("query_video_memory must be implemented in video-audit-service")
        elif name not in worker_text and name not in seed_text:
            fail(f"tool {name} is not referenced by worker or demo seed")

    for status in REQUIRED_STATUSES:
        if status not in worker_text and status not in ticket_text and status not in api_text:
            fail(f"status {status} is not referenced by backend code")


def validate_docs(names: list[str]) -> None:
    readme = read_text(README)
    for name in names:
        if name not in readme:
            fail(f"README Agent workflow table is missing {name}")
    if "config/safety_agent_workflow.json" not in readme:
        fail("README must link to the workflow spec")


def validate_mcp(spec: dict[str, Any]) -> None:
    exposed = set(spec.get("mcp_exposed_tools", []))
    if exposed != REQUIRED_MCP_TOOLS:
        fail(f"MCP tools mismatch: expected {sorted(REQUIRED_MCP_TOOLS)}, got {sorted(exposed)}")


def main() -> int:
    try:
        spec = load_spec()
        names = validate_tools(spec)
        validate_transitions(spec, names)
        validate_statuses(spec)
        validate_mcp(spec)
        validate_code_references(names)
        validate_docs(names)
    except Exception as exc:
        print(f"Workflow spec check failed: {exc}", file=sys.stderr)
        return 1
    print("Workflow spec check passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
