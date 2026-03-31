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
    # For tracking tasks in waiting_target state, autonomy receives patrol waypoints.
    # Expose those records in tracking/logs as well for easier end-to-end verification.
    tracking_patrol_logs = [
        item
        for item in collaboration_store.get_autonomy_patrol_logs()
        if str(item.get("task_type")) in {"tracking", "TaskType.TRACKING"}
    ]
    return ok({"items": tracking_logs + tracking_patrol_logs})
