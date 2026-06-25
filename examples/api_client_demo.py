"""Minimal stdlib client for the Industrial Video Safety Agent API."""

from __future__ import annotations

import argparse
import json
import sys
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


def request_json(method: str, url: str, payload: dict | None = None, token: str = "") -> dict | list:
    data = None
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
    req = Request(url, data=data, headers=headers, method=method)
    with urlopen(req, timeout=30) as resp:
        return json.loads(resp.read().decode("utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser(description="Read Agent metrics, explanation, and video memory from the safety platform.")
    parser.add_argument("--base-url", default="http://localhost:8000/api")
    parser.add_argument("--username", default="admin")
    parser.add_argument("--password", default="Admin123!")
    args = parser.parse_args()

    base = args.base_url.rstrip("/")
    try:
        login = request_json("POST", f"{base}/auth/login", {"username": args.username, "password": args.password})
        token = str(login["access_token"])

        metrics = request_json("GET", f"{base}/video-audits/metrics/evaluation", token=token)
        audits = request_json("GET", f"{base}/video-audits?{urlencode({'limit': 1})}", token=token)
        if not audits:
            print("No audits found. Run scripts/seed_demo_safety_agent.py first.")
            return 1

        audit = audits[0]
        audit_id = audit["id"]
        explanation = request_json("GET", f"{base}/video-audits/{audit_id}/agent-explanation", token=token)
        memory = request_json("GET", f"{base}/video-audits/{audit_id}/memory?{urlencode({'has_bbox': 'true'})}", token=token)

        print("Evaluation metrics")
        print(json.dumps(metrics, ensure_ascii=False, indent=2))
        print("\nLatest audit")
        print(json.dumps({"id": audit_id, "file_name": audit["file_name"], "risk_level": audit["risk_level"], "summary": audit["summary"]}, ensure_ascii=False, indent=2))
        print("\nAgent explanation")
        print(json.dumps(explanation, ensure_ascii=False, indent=2))
        print("\nVideo memory segments with bbox")
        print(json.dumps(memory, ensure_ascii=False, indent=2))
        return 0
    except HTTPError as exc:
        print(f"HTTP {exc.code}: {exc.read().decode('utf-8', errors='replace')}", file=sys.stderr)
        return 1
    except URLError as exc:
        print(f"Cannot reach API: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
