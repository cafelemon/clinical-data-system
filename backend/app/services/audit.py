import json
from typing import Any

from fastapi import Request
from fastapi.encoders import jsonable_encoder
from sqlalchemy.orm import Session

from app.api.deps import AccessContext
from app.models import OperationLog, User

SENSITIVE_KEYS = {
    "access_token",
    "content",
    "current_password",
    "file",
    "hashed_password",
    "new_password",
    "password",
    "raw",
    "token",
}
MAX_DETAIL_CHARS = 8000


def record_operation(
    db: Session,
    *,
    action: str,
    request: Request | None = None,
    access: AccessContext | None = None,
    user: User | None = None,
    username: str | None = None,
    target_type: str | None = None,
    target_id: int | None = None,
    project_id: int | None = None,
    center_id: int | None = None,
    detail: dict[str, Any] | None = None,
) -> OperationLog:
    actor = user
    if actor is None and access is not None:
        actor = access.user
    log = OperationLog(
        user_id=actor.id if actor is not None else None,
        username=username or (actor.username if actor is not None else None),
        action=action,
        target_type=target_type,
        target_id=target_id,
        project_id=project_id,
        center_id=center_id,
        ip_address=client_ip(request),
        user_agent=request.headers.get("user-agent") if request is not None else None,
        detail_json=sanitize_detail(detail or {}),
    )
    db.add(log)
    return log


def client_ip(request: Request | None) -> str | None:
    if request is None:
        return None
    forwarded_for = request.headers.get("x-forwarded-for")
    if forwarded_for:
        return forwarded_for.split(",", maxsplit=1)[0].strip()
    return request.client.host if request.client else None


def sanitize_detail(detail: dict[str, Any]) -> dict[str, Any]:
    encoded = jsonable_encoder(detail)
    redacted = redact(encoded)
    serialized = json.dumps(redacted, ensure_ascii=False, default=str)
    if len(serialized) <= MAX_DETAIL_CHARS:
        return redacted
    return {
        "truncated": True,
        "summary": "detail exceeded audit size limit",
        "keys": sorted(redacted.keys()) if isinstance(redacted, dict) else [],
    }


def redact(value: Any) -> Any:
    if isinstance(value, dict):
        clean: dict[str, Any] = {}
        for key, item in value.items():
            key_text = str(key)
            if key_text.lower() in SENSITIVE_KEYS:
                clean[key_text] = "[redacted]"
            else:
                clean[key_text] = redact(item)
        return clean
    if isinstance(value, list):
        return [redact(item) for item in value[:100]]
    if isinstance(value, str) and len(value) > 500:
        return f"{value[:500]}..."
    return value
