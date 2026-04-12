from fastapi import APIRouter, HTTPException, Query

from clients.media_client import media_client
from clients.sonar_client import sonar_client
from domain.models import (
    ManualSelectionFeedbackRequest,
    ManualSwitchFeedbackRequest,
    MediaStreamAccessRequest,
)
from domain.response import ok
from services.task_service import task_service
from store.collaboration_store import collaboration_store
from utils.time_utils import utc_now

router = APIRouter()


@router.get("/media/stream/access")
def get_media_stream_access(
    task_id: str = Query(...),
    stream_type: str = Query(...),
    channel_id: str = Query(...),
    media_protocol: str = Query(...),
):
    req = MediaStreamAccessRequest(
        task_id=task_id,
        stream_type=stream_type,
        channel_id=channel_id,
        media_protocol=media_protocol,
        request_time=utc_now(),
    )
    resp = media_client.get_stream_access(req)
    return resp


@router.post("/manual_selection/feedback")
def receive_manual_selection_feedback(req: ManualSelectionFeedbackRequest):
    try:
        task_service.apply_manual_selection_feedback(req)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    collaboration_store.append_manual_selection_feedback(req.model_dump(mode="json"))
    return ok({"task_id": req.task_id, "feedback_received": True})


@router.post("/manual_switch/feedback")
def receive_manual_switch_feedback(req: ManualSwitchFeedbackRequest):
    try:
        task_service.apply_manual_switch_feedback(req)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    collaboration_store.append_manual_switch_feedback(req.model_dump(mode="json"))
    return ok({"task_id": req.task_id, "feedback_received": True})


@router.get("/sonar/match/status")
def get_sonar_match_status(task_id: str = Query(...)):
    status = sonar_client.get_match_status(task_id)
    return ok(status.model_dump(mode="json"))
