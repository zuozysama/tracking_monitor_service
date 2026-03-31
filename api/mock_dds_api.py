from fastapi import APIRouter

from domain.models import MockDdsTargetsRequest, OwnShipState, UpdateTargetsRequest
from domain.response import ok
from store.situation_store import situation_store

router = APIRouter()


@router.post("/ownship")
def update_ownship(req: OwnShipState):
    situation_store.update_ownship(req)
    return ok({"platform_id": req.platform_id})


@router.post("/targets")
def update_targets(req: UpdateTargetsRequest):
    count = situation_store.update_targets(req.targets)
    return ok({"accepted_count": count})


@router.post("/navigation")
def update_navigation(req: OwnShipState):
    situation_store.update_ownship(req)
    return ok({"platform_id": req.platform_id})


@router.post("/perception")
def update_perception(req: MockDdsTargetsRequest):
    count = situation_store.update_targets(req.targets)
    return ok({"accepted_count": count})


@router.get("/situation")
def get_situation():
    return ok(
        {
            "ownship": situation_store.get_ownship(),
            "targets": situation_store.get_all_targets(),
        }
    )


@router.post("/reset")
def reset_situation():
    situation_store.reset()
    return ok({"reset": True})
