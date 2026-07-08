from __future__ import annotations

from adapters.dds.base import DdsAdapter
from domain.dds_contract import OWNSHIP_NAVIGATION_TOPIC, TARGET_PERCEPTION_TOPIC
from domain.models import OwnShipState, TargetState
from store.situation_store import situation_store
from utils.config_utils import get_dds_focus_platform_id, get_dds_target_enemy_friend_attrs
from utils.terminal import print_ownship_situation, print_targets_situation
from utils.time_utils import utc_now

_FOCUS_PLATFORM_ID = get_dds_focus_platform_id()

# Throttle counters: only print situation every N updates to avoid scroll flood.
_OWNship_PRINT_INTERVAL = 20
_TARGET_PRINT_INTERVAL = 10
_ownship_counter = 0
_target_counter = 0


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _on_ownship_message(data: dict) -> None:
    global _ownship_counter
    try:
        platform_id = _safe_int(data.get("platform_id", 0), 0)
        if platform_id != _FOCUS_PLATFORM_ID:
            return

        msg_ts = data.get("timestamp") or utc_now()
        model = OwnShipState(
            platform_id=platform_id,
            speed_mps=float(data.get("speed_mps", 0.0)),
            heading_deg=float(data.get("heading_deg", 0.0)) % 360.0,
            longitude=float(data.get("longitude", 0.0)),
            latitude=float(data.get("latitude", 0.0)),
            timestamp=msg_ts,
        )
        situation_store.update_ownship(model)

        _ownship_counter += 1
        if _ownship_counter >= _OWNship_PRINT_INTERVAL:
            _ownship_counter = 0
            print_ownship_situation(model)
    except Exception:
        return


def _on_target_perception_message(data: dict) -> None:
    targets_raw = data.get("targets") or []
    allowed_enemy_friend_attrs = get_dds_target_enemy_friend_attrs()
    models: list[TargetState] = []
    for item in targets_raw:
        try:
            batch_no = _safe_int(item.get("target_batch_no"), 0)
            enemy_friend_attr = _safe_int(item.get("enemy_friend_attr"), 0)
            if allowed_enemy_friend_attrs is not None and enemy_friend_attr not in allowed_enemy_friend_attrs:
                continue

            # Keep military/civil attribute for downstream visibility only.
            # It must not decide whether a target enters the situation store.
            military_civil_attr = _safe_int(item.get("military_civil_attr"), 0)

            msg_ts = item.get("timestamp") or data.get("timestamp") or utc_now()
            models.append(
                TargetState(
                    source_platform_id=item.get("source_platform_id"),
                    target_id=item.get("target_id"),
                    target_batch_no=batch_no,
                    target_position_attr=item.get("target_position_attr"),
                    target_length_m=item.get("target_length_m"),
                    target_bearing_deg=float(item.get("target_bearing_deg", 0.0)) % 360.0,
                    target_distance_m=float(item.get("target_distance_m", 0.0)),
                    target_absolute_speed_mps=float(item.get("target_absolute_speed_mps", 0.0)),
                    target_absolute_heading_deg=float(item.get("target_absolute_heading_deg", 0.0)) % 360.0,
                    target_longitude=float(item.get("target_longitude", 0.0)),
                    target_latitude=float(item.get("target_latitude", 0.0)),
                    target_type_code=item.get("target_type_code"),
                    enemy_friend_attr=enemy_friend_attr,
                    military_civil_attr=military_civil_attr,
                    target_name=item.get("target_name"),
                    threat_level=item.get("threat_level"),
                    timestamp=msg_ts,
                    active=True,
                )
            )
        except Exception:
            continue

    revision_raw = _safe_int(data.get("revision"), 0)
    revision = revision_raw if revision_raw > 0 else None
    source_id = data.get("source_id")
    if source_id is not None:
        source_id = str(source_id)

    # Unified dynamic retention:
    # always upsert incoming targets and prune stale unseen targets by timeout.
    result = situation_store.update_targets(models, revision=revision, source_id=source_id)

    global _target_counter
    if result.accepted and models:
        _target_counter += 1
        if _target_counter >= _TARGET_PRINT_INTERVAL:
            _target_counter = 0
            snapshot = situation_store.get_situation_snapshot()
            all_targets = snapshot.get("targets", [])
            print_targets_situation(len(all_targets), all_targets)


def register_default_subscriptions(dds_adapter: DdsAdapter) -> None:
    dds_adapter.subscribe(OWNSHIP_NAVIGATION_TOPIC, _on_ownship_message)
    dds_adapter.subscribe(TARGET_PERCEPTION_TOPIC, _on_target_perception_message)
