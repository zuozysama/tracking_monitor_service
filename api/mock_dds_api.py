from fastapi import APIRouter

from adapters.dds import get_dds_adapter
from domain.dds_contract import OWNSHIP_NAVIGATION_TOPIC, TARGET_PERCEPTION_TOPIC
from domain.models import MockDdsTargetsRequest, OwnShipState, UpdateTargetsRequest
from domain.response import ok
from store.situation_store import situation_store

router = APIRouter()
dds_adapter = get_dds_adapter()


@router.post("/ownship")
def update_ownship(req: OwnShipState):
    situation_store.update_ownship(req)
    dds_adapter.publish(topic=OWNSHIP_NAVIGATION_TOPIC, payload=req.model_dump(mode="json"))
    return ok({"platform_id": req.platform_id})


@router.post("/targets")
def update_targets(req: UpdateTargetsRequest):
    count = situation_store.update_targets(req.targets)
    dds_adapter.publish(topic=TARGET_PERCEPTION_TOPIC, payload=req.model_dump(mode="json"))
    return ok({"accepted_count": count})


@router.post("/navigation")
def update_navigation(req: OwnShipState):
    situation_store.update_ownship(req)
    dds_adapter.publish(topic=OWNSHIP_NAVIGATION_TOPIC, payload=req.model_dump(mode="json"))
    return ok({"platform_id": req.platform_id})


@router.post("/perception")
def update_perception(req: MockDdsTargetsRequest):
    count = situation_store.update_targets(req.targets)
    dds_adapter.publish(topic=TARGET_PERCEPTION_TOPIC, payload=req.model_dump(mode="json"))
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
