"""Audit log read-only endpoint."""
from __future__ import annotations

from fastapi import APIRouter, Depends

from app import audit as audit_module
from app.auth.middleware import require_session
from app.auth.session import Session
from shared.models import AuditPage

router = APIRouter(prefix="/api/audit", tags=["audit"])


@router.get("", response_model=AuditPage)
async def list_audit(
    page: int = 1,
    page_size: int = 50,
    plugin_slug: str | None = None,
    session: Session = Depends(require_session),
) -> AuditPage:
    return audit_module.list_entries(
        page=page,
        page_size=page_size,
        plugin_slug=plugin_slug,
    )
