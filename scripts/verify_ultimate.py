import json
import os
import sys
import time
import urllib.parse
import urllib.request


if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

BASE_URL = os.environ.get("AICODING_API_BASE", "http://localhost:8000/api").rstrip("/")
USERNAME = os.environ.get("AICODING_ADMIN_USERNAME", "admin")
PASSWORD = os.environ.get("AICODING_ADMIN_PASSWORD", "Admin123!")


def request(method: str, path: str, payload: dict | None = None, token: str | None = None):
    data = None if payload is None else json.dumps(payload, ensure_ascii=False).encode("utf-8")
    headers = {"Content-Type": "application/json; charset=utf-8"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = urllib.request.Request(f"{BASE_URL}{path}", data=data, headers=headers, method=method)
    with urllib.request.urlopen(req, timeout=60) as resp:
        body = resp.read().decode("utf-8")
        return json.loads(body) if body else None


def assert_true(condition: bool, message: str):
    if not condition:
        raise AssertionError(message)


def main():
    login = request("POST", "/auth/login", {"username": USERNAME, "password": PASSWORD})
    token = login["access_token"]

    request("POST", "/kb/seed/ecommerce", token=token)

    refund_question = "\u6211\u60f3\u9000\u6b3e\u591a\u4e45\u5230\u8d26\uff1f"
    query = urllib.parse.urlencode({"q": refund_question, "include_trace": "true"})
    rag = request("GET", f"/kb/search?{query}", token=token)
    assert_true(rag["sources"], "RAG returned no sources")
    assert_true(rag["sources"][0]["title"] == "\u9000\u6b3e\u89c4\u5219", "refund query did not hit refund policy")
    assert_true(rag["confidence"] >= 0.7, "refund query confidence is too low")
    assert_true(rag["retrieval_trace"]["vector_candidates"] > 0, "Milvus vector recall returned no candidates")

    suffix = str(int(time.time()))
    knowledge_title = f"Ultimate Acceptance Policy {suffix}"
    knowledge_keyword = f"ultimate-acceptance-{suffix}"
    document = request(
        "POST",
        "/kb/documents",
        {
            "title": knowledge_title,
            "category": "acceptance",
            "content": f"{knowledge_keyword} customers receive a dedicated acceptance answer.",
            "source": "verify_ultimate",
            "license": "internal",
        },
        token=token,
    )
    approved = request("POST", "/kb/approvals", {"document_id": document["id"], "approved": True}, token=token)
    assert_true(approved["status"] == "approved", "knowledge document was not approved")
    published = request("POST", "/kb/publish", {"document_id": document["id"], "approved": True}, token=token)
    assert_true(published["status"] == "published", "knowledge document was not published")
    custom_query = urllib.parse.urlencode({"q": knowledge_keyword, "include_trace": "true"})
    custom_rag = request("GET", f"/kb/search?{custom_query}", token=token)
    assert_true(any(source["title"] == knowledge_title for source in custom_rag["sources"]), "published knowledge was not searchable")

    session = request("POST", "/chat/sessions", {"visitor_name": "\u7ec8\u6781\u7248\u9a8c\u6536"}, token=token)
    messages = request(
        "POST",
        f"/chat/sessions/{session['id']}/messages",
        {"content": "\u6211\u8981\u6295\u8bc9\uff0c\u627e\u4eba\u5de5"},
        token=token,
    )
    last_message = messages[-1]
    assert_true("complaint" in last_message["risk_tags"], "complaint risk tag was not detected")
    assert_true("handoff" in last_message["risk_tags"], "handoff risk tag was not detected")

    rating = request("POST", f"/chat/sessions/{session['id']}/satisfaction", {"score": 4}, token=token)
    assert_true(rating["satisfaction"] == 4, "satisfaction rating was not saved")

    ticket = request(
        "POST",
        "/tickets",
        {
            "title": f"Ultimate acceptance ticket {suffix}",
            "description": "Created by terminal verification.",
            "conversation_id": session["id"],
            "priority": "high",
        },
        token=token,
    )
    patched_ticket = request("PATCH", f"/tickets/{ticket['id']}", {"status": "pending"}, token=token)
    assert_true(patched_ticket["status"] == "pending", "ticket status was not updated")
    request("POST", f"/tickets/{ticket['id']}/comments", {"content": "Verification comment.", "internal": True}, token=token)
    flow_logs = request("GET", f"/tickets/{ticket['id']}/flow-logs", token=token)
    assert_true(len(flow_logs) >= 3, "ticket flow logs are incomplete")

    channels = request("GET", "/channels", token=token)
    if channels:
        channel = channels[0]
    else:
        channel = request("POST", "/channels", {"name": f"Verify Web {suffix}", "type": "web"}, token=token)
    simulated = request(
        "POST",
        f"/channels/{channel['id']}/simulate-webhook",
        {
            "visitor_name": "\u6e20\u9053\u9a8c\u6536",
            "content": "\u53d1\u7968\u600e\u4e48\u5f00",
            "external_id": f"verify-{suffix}",
        },
        token=token,
    )
    assert_true(simulated["adapter"] == "webhook-simulation", "channel simulation did not use adapter simulation")
    assert_true(simulated["conversation"]["id"] > 0, "channel simulation did not create a conversation")

    provider = request(
        "POST",
        "/models/providers",
        {"name": f"Verify Mock Provider {suffix}", "provider_type": "mock", "model": "mock-local", "enabled": True},
        token=token,
    )
    route = request("POST", "/models/routes", {"name": f"Verify Route {suffix}", "provider_id": provider["id"]}, token=token)
    prompt = request("POST", "/prompts/versions", {"template_name": f"Verify Prompt {suffix}", "content": "Answer only from knowledge."}, token=token)
    assert_true(route["provider_id"] == provider["id"], "model route was not linked to provider")
    assert_true(prompt["version"] == 1, "prompt version was not created")

    quality = request("POST", "/quality/reports/run", token=token)
    assert_true(quality["status"] == "completed", "quality report task did not complete")
    assert_true(quality["reports_created"] >= 1, "quality report task did not create reports")

    audit = request("GET", "/audit/logs", token=token)
    assert_true(audit and audit[0]["tenant_id"] == 1, "audit log missing tenant context")

    health = request("GET", "/system/health", token=token)
    for dependency in ("postgres", "milvus", "redis", "worker"):
        assert_true(health[dependency] == "ok", f"{dependency} health is not ok")

    result = {
        "status": "passed",
        "base_url": BASE_URL,
        "rag": {
            "top_source": rag["sources"][0]["title"],
            "confidence": rag["confidence"],
            "vector_candidates": rag["retrieval_trace"]["vector_candidates"],
            "keyword_candidates": rag["retrieval_trace"]["keyword_candidates"],
        },
        "conversation_id": session["id"],
        "risk_tags": last_message["risk_tags"],
        "knowledge_governance": {
            "document_id": document["id"],
            "published_version": published["version"],
            "searchable": True,
        },
        "ticket": {"id": ticket["id"], "flow_logs": len(flow_logs)},
        "channel_simulation": {"channel_id": channel["id"], "conversation_id": simulated["conversation"]["id"]},
        "model_governance": {"provider_id": provider["id"], "route_id": route["id"], "prompt_version_id": prompt["id"]},
        "quality_run": quality,
        "health": health,
        "latest_audit_action": audit[0]["action"],
    }
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    try:
        main()
    except Exception as exc:
        print(json.dumps({"status": "failed", "error": str(exc)}, ensure_ascii=False), file=sys.stderr)
        raise
