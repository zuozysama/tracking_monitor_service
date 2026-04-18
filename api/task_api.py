from fastapi import APIRouter, HTTPException
from typing import Optional

from domain.models import (
    CreateTaskRequest,
    FeasibilityCallbackRequest,
    GeoPoint,
    TaskContext,
    TerminateTaskRequest,
)
from domain.response import ok
from services.task_service import task_service
from utils.geo_utils import haversine_distance_m

router = APIRouter()


def _build_preplan_result(task: TaskContext) -> Optional[dict]:
    if task.preplan_output is None:
        return None

    planned_route = task.preplan_output.planned_route or []
    route_items: list[dict] = []
    accumulated_eta_sec = 0.0

    for idx, waypoint in enumerate(planned_route):
        point_type = "normal"
        if idx == 0:
            point_type = "start"
        elif idx == len(planned_route) - 1:
            point_type = "end"

        item = {
            "longitude": waypoint.longitude,
            "latitude": waypoint.latitude,
            "expected_speed": waypoint.expected_speed,
            "point_type": point_type,
        }

        if idx == 0:
            item["eta_sec"] = 0
        else:
            previous = planned_route[idx - 1]
            speed_mps = waypoint.expected_speed or previous.expected_speed or task.expected_speed or 0.0
            if speed_mps > 0:
                segment_distance_m = haversine_distance_m(
                    GeoPoint(longitude=previous.longitude, latitude=previous.latitude),
                    GeoPoint(longitude=waypoint.longitude, latitude=waypoint.latitude),
                )
                accumulated_eta_sec += segment_distance_m / speed_mps
                item["eta_sec"] = int(round(accumulated_eta_sec))

        route_items.append(item)

    return {
        "plan_type": "preplan",
        "waypoint_count": len(route_items),
        "planned_route": route_items,
    }


@router.post("/tasks")
def create_task(req: CreateTaskRequest):
    try:
        task = task_service.create_task(req)
        payload = {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "task_name": task.task_name,
            "task_status": task.status,
            "execution_phase": task.execution_phase,
            "create_time": task.create_time,
            "start_time": task.start_time,
            "update_time": task.update_time,
        }
        preplan_result = _build_preplan_result(task)
        if preplan_result is not None:
            payload["preplan_result"] = preplan_result
        return ok(payload)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/tasks")
def list_tasks():
    tasks = task_service.list_tasks()
    items = [
        {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "task_status": task.status,
            "update_time": task.update_time,
        }
        for task in tasks
    ]
    return ok({"items": items})


@router.get("/{task_id}/status")
def get_task_status(task_id: str):
    try:
        result = task_service.get_status(task_id)
        return ok(result.model_dump())
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{task_id}/manual_selection/status")
def get_manual_selection_status(task_id: str):
    try:
        result = task_service.get_manual_selection_status(task_id)
        return ok(result)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{task_id}/manual_switch/status")
def get_manual_switch_status(task_id: str):
    try:
        result = task_service.get_manual_switch_status(task_id)
        return ok(result)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{task_id}/result")
def get_task_result(task_id: str):
    try:
        result = task_service.get_result(task_id)
        return ok(result.model_dump())
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{task_id}/output")
def get_task_output(task_id: str):
    try:
        result = task_service.get_output(task_id)
        return ok(result.model_dump())
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/tasks/{task_id}/terminate")
def terminate_task(task_id: str, req: TerminateTaskRequest):
    try:
        task = task_service.terminate_task(task_id, reason=req.reason)
        return ok(
            {
                "task_id": task.task_id,
                "task_status": task.status,
                "execution_phase": task.execution_phase,
                "finish_reason": task.finish_reason,
                "end_time": task.end_time,
                "update_time": task.update_time,
            }
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.post("/callbacks/planning/feasibility")
def planning_feasibility_callback(req: FeasibilityCallbackRequest):
    try:
        task = task_service.apply_planning_callback(req)
        return ok(
            {
                "task_id": task.task_id,
                "callback_received": True,
            }
        )
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))
