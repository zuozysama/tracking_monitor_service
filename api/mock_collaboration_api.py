from typing import Optional

from fastapi import APIRouter

from adapters.dds import get_dds_adapter
from domain.dds_contract import OWNSHIP_NAVIGATION_TOPIC, TARGET_PERCEPTION_TOPIC
from domain.models import OptronicStatus, SonarMatchStatus
from domain.response import ok
from store.collaboration_store import collaboration_store
from utils.time_utils import utc_now

router = APIRouter()


@router.get("/optronic/{task_id}/status")
def get_optronic_status(task_id: str):
    status = collaboration_store.get_optronic_status(task_id)
    return ok(status.model_dump())


@router.post("/optronic/{task_id}/status")
def set_optronic_status(task_id: str, req: OptronicStatus):
    collaboration_store.set_optronic_status(task_id, req)
    return ok(req.model_dump())


@router.get("/media/photos")
def get_photo_logs():
    return ok({"items": collaboration_store.get_photo_logs()})


@router.get("/media/videos")
def get_video_logs():
    return ok({"items": collaboration_store.get_video_logs()})


@router.get("/media/stream-access")
def get_media_stream_access_logs():
    return ok({"items": collaboration_store.get_media_stream_access_logs()})


@router.get("/planning/stages")
def get_stage_logs():
    return ok({"items": collaboration_store.get_stage_logs()})


@router.get("/planning/plans")
def get_plan_logs():
    return ok({"items": collaboration_store.get_plan_logs()})


@router.get("/optical-linkage/commands")
def get_optical_linkage_commands():
    return ok({"items": collaboration_store.get_optical_linkage_logs()})


@router.get("/manual-selection/requests")
def get_manual_selection_requests():
    return ok({"items": collaboration_store.get_manual_selection_requests()})


@router.get("/manual-switch/requests")
def get_manual_switch_requests():
    return ok({"items": collaboration_store.get_manual_switch_requests()})


@router.get("/manual-selection/feedbacks")
def get_manual_selection_feedbacks():
    return ok({"items": collaboration_store.get_manual_selection_feedbacks()})


@router.get("/manual-switch/feedbacks")
def get_manual_switch_feedbacks():
    return ok({"items": collaboration_store.get_manual_switch_feedbacks()})


@router.get("/dds/publish-logs")
def get_dds_publish_logs():
    return ok({"items": collaboration_store.get_dds_publish_logs()})


@router.get("/dds/subscribe-logs")
def get_dds_subscribe_logs(topic: Optional[str] = None, limit: int = 100):
    limit = max(1, min(limit, 1000))
    items = collaboration_store.get_dds_subscribe_logs()
    if topic:
        items = [x for x in items if x.get("topic") == topic]
    return ok({"items": items[-limit:]})


@router.get("/dds/debug-status")
def get_dds_debug_status():
    adapter = get_dds_adapter()
    publish_logs = collaboration_store.get_dds_publish_logs()
    subscribe_logs = collaboration_store.get_dds_subscribe_logs()
    recent_errors = [
        x
        for x in publish_logs
        if str(x.get("adapter", "")).startswith("real-") and ("error" in str(x.get("adapter", "")) or "fallback" in str(x.get("adapter", "")))
    ][-20:]
    return ok(
        {
            "adapter_class": adapter.__class__.__name__,
            "expected_subscribe_topics": [
                OWNSHIP_NAVIGATION_TOPIC,
                TARGET_PERCEPTION_TOPIC,
            ],
            "adapter_runtime": {
                "started": bool(getattr(adapter, "_started", False)),
                "sdk_loaded": bool(getattr(adapter, "_sdk_loaded", False)),
                "load_error": str(getattr(adapter, "_load_error", "")),
                "qos_profile": str(getattr(adapter, "_qos_profile", "")),
                "subscribed_topics": sorted(list(getattr(adapter, "_sub_topics", set()))),
                "registered_handlers": sorted(list(getattr(adapter, "_sub_handlers", {}).keys())),
            },
            "log_stats": {
                "publish_log_count": len(publish_logs),
                "subscribe_log_count": len(subscribe_logs),
            },
            "latest_subscribe_sample": subscribe_logs[-1] if subscribe_logs else None,
            "recent_errors": recent_errors,
            "hints": [
                "If subscribe_log_count is 0, check publisher topic/type/domain/qos compatibility.",
                "type_name must be CSMXP_V3 for current listener implementation.",
                "send_task_tracking.sh only creates tasks via HTTP; it does not produce inbound DDS subscribe traffic.",
            ],
        }
    )


@router.get("/sonar/{task_id}/status")
def get_sonar_status(task_id: str):
    status = collaboration_store.get_sonar_status(task_id)
    return ok(status.model_dump())


@router.post("/sonar/{task_id}/status")
def set_sonar_status(task_id: str, req: SonarMatchStatus):
    collaboration_store.set_sonar_status(task_id, req)
    return ok(req.model_dump())


@router.post("/reset_optronic/{task_id}")
def reset_optronic(task_id: str):
    status = OptronicStatus(
        is_power_on=False,
        last_horizontal_angle_deg=None,
        update_time=utc_now(),
    )
    collaboration_store.set_optronic_status(task_id, status)
    return ok(status.model_dump())


@router.post("/reset")
def reset_collaboration_store():
    collaboration_store.reset()
    return ok({"reset": True})
