from fastapi import APIRouter, HTTPException

from domain.models import (
    CreateTaskRequest,
    FeasibilityCallbackRequest,
    TerminateTaskRequest,
)
from domain.response import ok
from services.task_service import task_service

router = APIRouter()


@router.post("")
def create_task(req: CreateTaskRequest):
    try:
        task = task_service.create_task(req)
        return ok(
            {
                "task_id": task.task_id,
                "task_type": task.task_type,
                "task_name": task.task_name,
                "task_status": task.status,
                "execution_phase": task.execution_phase,
                "create_time": task.create_time,
                "start_time": task.start_time,
                "update_time": task.update_time,
            }
        )
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("")
def list_tasks():
    tasks = task_service.list_tasks()
    items = [
        {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "mode": task.mode,
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


@router.get("/{task_id}/manual-selection/status")
def get_manual_selection_status(task_id: str):
    try:
        result = task_service.get_manual_selection_status(task_id)
        return ok(result)
    except LookupError as e:
        raise HTTPException(status_code=404, detail=str(e))


@router.get("/{task_id}/manual-switch/status")
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


@router.post("/{task_id}/terminate")
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
