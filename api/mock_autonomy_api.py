from fastapi import APIRouter

from domain.response import ok
from store.collaboration_store import collaboration_store

router = APIRouter()


@router.get("/patrol/logs")
def get_autonomy_patrol_logs():
    return ok({"items": collaboration_store.get_autonomy_patrol_logs()})


@router.get("/tracking/logs")
def get_autonomy_tracking_logs():
    tracking_logs = collaboration_store.get_autonomy_tracking_logs()
    # New autonomy payload no longer carries task_type on patrol dispatch,
    # so expose patrol logs directly for end-to-end verification.
    tracking_patrol_logs = collaboration_store.get_autonomy_patrol_logs()
    return ok({"items": tracking_logs + tracking_patrol_logs})


@router.get("/http-dispatch-logs")
def get_autonomy_http_dispatch_logs(limit: int = 100):
    limit = max(1, min(limit, 1000))
    items = collaboration_store.get_autonomy_http_dispatch_logs()
    return ok({"items": items[-limit:]})
