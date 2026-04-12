from __future__ import annotations

from adapters.dds.base import DdsAdapter
from domain.dds_contract import OWNSHIP_NAVIGATION_TOPIC, TARGET_PERCEPTION_TOPIC
from domain.models import OwnShipState, TargetState
from store.situation_store import situation_store
from utils.time_utils import utc_now


def _on_ownship_message(data: dict) -> None:
    try:
        model = OwnShipState(
            platform_id=int(data.get("platform_id", 0)),
            speed_mps=float(data.get("speed_mps", 0.0)),
            heading_deg=float(data.get("heading_deg", 0.0)) % 360.0,
            longitude=float(data.get("longitude", 0.0)),
            latitude=float(data.get("latitude", 0.0)),
            timestamp=utc_now(),
        )
        situation_store.update_ownship(model)
    except Exception:
        return


def _on_target_perception_message(data: dict) -> None:
    targets_raw = data.get("targets") or []
    models: list[TargetState] = []
    for item in targets_raw:
        try:
            models.append(
                TargetState(
                    source_platform_id=item.get("source_platform_id"),
                    target_id=item.get("target_id"),
                    target_batch_no=int(item.get("target_batch_no", 0)),
                    target_bearing_deg=float(item.get("target_bearing_deg", 0.0)) % 360.0,
                    target_distance_m=float(item.get("target_distance_m", 0.0)),
                    target_absolute_speed_mps=float(item.get("target_absolute_speed_mps", 0.0)),
                    target_absolute_heading_deg=float(item.get("target_absolute_heading_deg", 0.0)) % 360.0,
                    target_longitude=float(item.get("target_longitude", 0.0)),
                    target_latitude=float(item.get("target_latitude", 0.0)),
                    target_type_code=item.get("target_type_code"),
                    military_civil_attr=item.get("military_civil_attr"),
                    threat_level=item.get("threat_level"),
                    timestamp=utc_now(),
                    active=True,
                )
            )
        except Exception:
            continue

    if models:
        situation_store.update_targets(models)


def register_default_subscriptions(dds_adapter: DdsAdapter) -> None:
    dds_adapter.subscribe(OWNSHIP_NAVIGATION_TOPIC, _on_ownship_message)
    dds_adapter.subscribe(TARGET_PERCEPTION_TOPIC, _on_target_perception_message)
