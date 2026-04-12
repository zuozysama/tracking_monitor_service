from fastapi import APIRouter

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
