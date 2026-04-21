from typing import Literal, Optional, Union

from fastapi import APIRouter

from adapters.dds import get_dds_adapter
from domain.dds_contract import OWNSHIP_NAVIGATION_TOPIC, TARGET_PERCEPTION_TOPIC
from domain.models import MockDdsTargetsRequest, OwnShipState, UpdateTargetsRequest
from domain.response import ok
from store.situation_store import situation_store

router = APIRouter()
dds_adapter = get_dds_adapter()


def _resolve_sync_mode(
    request_sync_mode: Optional[Literal["replace", "merge"]],
    payload_sync_mode: Optional[Literal["replace", "merge"]],
    is_full_snapshot: Optional[bool],
) -> Literal["replace", "merge"]:
    if is_full_snapshot is True:
        return "replace"
    if request_sync_mode in {"replace", "merge"}:
        return request_sync_mode
    if payload_sync_mode in {"replace", "merge"}:
        return payload_sync_mode
    return "replace"


def _sync_targets(
    req: Union[UpdateTargetsRequest, MockDdsTargetsRequest],
    request_sync_mode: Optional[Literal["replace", "merge"]],
):
    sync_mode = _resolve_sync_mode(request_sync_mode, req.sync_mode, req.is_full_snapshot)
    if sync_mode == "replace":
        result = situation_store.replace_targets(
            req.targets,
            revision=req.revision,
            source_id=req.source_id,
        )
    else:
        result = situation_store.update_targets(
            req.targets,
            revision=req.revision,
            source_id=req.source_id,
        )
    return sync_mode, result


@router.post("/ownship")
def update_ownship(req: OwnShipState):
    situation_store.update_ownship(req)
    dds_adapter.publish(topic=OWNSHIP_NAVIGATION_TOPIC, payload=req.model_dump(mode="json"))
    return ok({"platform_id": req.platform_id})


@router.post("/targets")
def update_targets(
    req: UpdateTargetsRequest,
    sync_mode: Optional[Literal["replace", "merge"]] = None,
):
    resolved_sync_mode, result = _sync_targets(req, sync_mode)
    dds_adapter.publish(topic=TARGET_PERCEPTION_TOPIC, payload=req.model_dump(mode="json"))
    return ok(
        {
            "accepted": result.accepted,
            "accepted_count": result.input_count if result.accepted else 0,
            "total_count": result.total_count,
            "revision": result.revision,
            "sync_mode": resolved_sync_mode,
            "ignored_stale_revision": result.ignored_stale_revision,
        }
    )


@router.post("/navigation")
def update_navigation(req: OwnShipState):
    situation_store.update_ownship(req)
    dds_adapter.publish(topic=OWNSHIP_NAVIGATION_TOPIC, payload=req.model_dump(mode="json"))
    return ok({"platform_id": req.platform_id})


@router.post("/perception")
def update_perception(
    req: MockDdsTargetsRequest,
    sync_mode: Optional[Literal["replace", "merge"]] = None,
):
    resolved_sync_mode, result = _sync_targets(req, sync_mode)
    dds_adapter.publish(topic=TARGET_PERCEPTION_TOPIC, payload=req.model_dump(mode="json"))
    return ok(
        {
            "accepted": result.accepted,
            "accepted_count": result.input_count if result.accepted else 0,
            "total_count": result.total_count,
            "revision": result.revision,
            "sync_mode": resolved_sync_mode,
            "ignored_stale_revision": result.ignored_stale_revision,
        }
    )


@router.get("/situation")
def get_situation():
    snapshot = situation_store.get_situation_snapshot()
    return ok(
        {
            "ownship": snapshot["ownship"],
            "targets": snapshot["targets"],
            "revision": snapshot["revision"],
            "target_count": len(snapshot["targets"]),
            "last_source_id": snapshot["last_source_id"],
            "last_update_time": snapshot["last_update_time"],
        }
    )


@router.post("/reset")
def reset_situation():
    situation_store.reset()
    return ok(
        {
            "reset": True,
            "debug_only": True,
            "notice": "debug-only endpoint; do not use in normal business flow",
        }
    )
