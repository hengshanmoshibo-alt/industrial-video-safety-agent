import httpx
from fastapi import Request, Response
from jose import JWTError, jwt
from redis import Redis
from sqlmodel import Session

from aicoding_shared.config import get_settings
from aicoding_shared.db import engine
from aicoding_shared.models import AuditLog
from aicoding_shared.service import create_service_app


app = create_service_app("api-gateway")

ALGORITHM = "HS256"
WRITE_METHODS = {"POST", "PUT", "PATCH", "DELETE"}


ROUTES: list[tuple[str, str]] = [
    ("/api/auth", "auth_service_url"),
    ("/api/users", "auth_service_url"),
    ("/api/tenants", "auth_service_url"),
    ("/api/departments", "auth_service_url"),
    ("/api/roles", "auth_service_url"),
    ("/api/chat", "conversation_service_url"),
    ("/api/agent", "conversation_service_url"),
    ("/api/tickets", "ticket_service_url"),
    ("/api/kb", "knowledge_service_url"),
    ("/api/models", "ai_orchestrator_url"),
    ("/api/prompts", "ai_orchestrator_url"),
    ("/api/model-call-logs", "ai_orchestrator_url"),
    ("/api/channels", "channel_service_url"),
    ("/api/analytics", "analytics_service_url"),
    ("/api/audit", "analytics_service_url"),
    ("/api/quality", "analytics_service_url"),
    ("/api/system", "analytics_service_url"),
    ("/api/video-audits", "video_audit_service_url"),
    ("/api/safety-policies", "video_audit_service_url"),
    ("/api/safety-tools", "video_audit_service_url"),
]


def _target_for(path: str) -> tuple[str, str]:
    settings = get_settings()
    for prefix, attr in ROUTES:
        if path.startswith(prefix):
            base = getattr(settings, attr).rstrip("/")
            return base, path.removeprefix("/api")
    return settings.analytics_service_url.rstrip("/"), path.removeprefix("/api")


def _token_context(request: Request) -> tuple[int | None, int | None]:
    auth = request.headers.get("authorization", "")
    if not auth.lower().startswith("bearer "):
        return None, None
    try:
        payload = jwt.decode(auth.split(" ", 1)[1], get_settings().secret_key, algorithms=[ALGORITHM])
        return int(payload.get("tenant_id")) if payload.get("tenant_id") is not None else None, int(payload.get("user_id")) if payload.get("user_id") is not None else None
    except (JWTError, ValueError, TypeError):
        return None, None


def _rate_limited(request: Request) -> bool:
    settings = get_settings()
    client = request.client.host if request.client else "unknown"
    tenant_id, user_id = _token_context(request)
    identity = user_id or tenant_id or client
    key = f"ratelimit:{identity}:{request.url.path}"
    try:
        redis = Redis.from_url(settings.redis_url, socket_connect_timeout=1, socket_timeout=1)
        count = redis.incr(key)
        if count == 1:
            redis.expire(key, 60)
        return count > 120
    except Exception:
        return False


def _write_audit(request: Request, status_code: int) -> None:
    if request.method not in WRITE_METHODS:
        return
    tenant_id, user_id = _token_context(request)
    with Session(engine) as session:
        session.add(
            AuditLog(
                tenant_id=tenant_id,
                actor_id=user_id,
                action=f"{request.method} {request.url.path}",
                target_type="api",
                target_id=request.path_params.get("path", ""),
                detail={"status_code": status_code},
            )
        )
        session.commit()


@app.api_route("/api/{path:path}", methods=["GET", "POST", "PUT", "PATCH", "DELETE"])
async def proxy(path: str, request: Request):
    if path == "system/gateway":
        return {"status": "ok", "routes": [prefix for prefix, _ in ROUTES]}
    if _rate_limited(request):
        return Response(content='{"detail":"Rate limit exceeded"}', status_code=429, media_type="application/json")
    base, upstream_path = _target_for(f"/api/{path}")
    url = f"{base}{upstream_path}"
    headers = {key: value for key, value in request.headers.items() if key.lower() not in {"host", "content-length"}}
    tenant_id, user_id = _token_context(request)
    if tenant_id is not None:
        headers["X-Tenant-Id"] = str(tenant_id)
    if user_id is not None:
        headers["X-User-Id"] = str(user_id)
    body = await request.body()
    timeout = httpx.Timeout(300.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        upstream = await client.request(request.method, url, params=request.query_params, content=body, headers=headers)
    _write_audit(request, upstream.status_code)
    excluded = {"content-encoding", "transfer-encoding", "connection"}
    response_headers = {key: value for key, value in upstream.headers.items() if key.lower() not in excluded}
    return Response(content=upstream.content, status_code=upstream.status_code, headers=response_headers, media_type=upstream.headers.get("content-type"))


@app.get("/api/system/gateway")
def gateway_health():
    return {"status": "ok", "routes": [prefix for prefix, _ in ROUTES]}
