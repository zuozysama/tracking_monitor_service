from __future__ import annotations

from adapters.dds.base import DdsAdapter
from domain.dds_contract import OWNSHIP_NAVIGATION_TOPIC, TARGET_PERCEPTION_TOPIC
from domain.models import OwnShipState, TargetState
from store.situation_store import situation_store
from utils.config_utils import get_dds_focus_platform_id, get_dds_target_sync_mode
from utils.time_utils import utc_now

_FOCUS_PLATFORM_ID = get_dds_focus_platform_id()
_TARGET_SYNC_MODE = get_dds_target_sync_mode()


def _safe_int(value, default: int = 0) -> int:
    try:
        return int(value)
    except Exception:
        return default


def _safe_bool(value, default: bool = False) -> bool:
    if value is None:
        return default
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"1", "true", "yes", "on"}:
            return True
        if normalized in {"0", "false", "no", "off"}:
            return False
    return bool(value)


def _resolve_target_sync_mode(data: dict) -> str:
    if _safe_bool(data.get("is_full_snapshot"), False):
        return "replace"
    raw_mode = str(data.get("sync_mode", "")).strip().lower()
    if raw_mode in {"replace", "merge"}:
        return raw_mode
    return _TARGET_SYNC_MODE


def _on_ownship_message(data: dict) -> None:
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
    except Exception:
        return


def _on_target_perception_message(data: dict) -> None:
    source_platform_id = _safe_int(data.get("source_platform_id"), -1)
    if source_platform_id >= 0 and source_platform_id != _FOCUS_PLATFORM_ID:
        return

    targets_raw = data.get("targets") or []
    models: list[TargetState] = []
    for item in targets_raw:
        try:
            item_source = _safe_int(item.get("source_platform_id"), -1)
            if item_source >= 0 and item_source != _FOCUS_PLATFORM_ID:
                continue

            msg_ts = item.get("timestamp") or data.get("timestamp") or utc_now()
            models.append(
                TargetState(
                    source_platform_id=item.get("source_platform_id"),
                    target_id=item.get("target_id"),
                    target_batch_no=int(item.get("target_batch_no", 0)),
                    target_position_attr=item.get("target_position_attr"),
                    target_length_m=item.get("target_length_m"),
                    target_bearing_deg=float(item.get("target_bearing_deg", 0.0)) % 360.0,
                    target_distance_m=float(item.get("target_distance_m", 0.0)),
                    target_absolute_speed_mps=float(item.get("target_absolute_speed_mps", 0.0)),
                    target_absolute_heading_deg=float(item.get("target_absolute_heading_deg", 0.0)) % 360.0,
                    target_longitude=float(item.get("target_longitude", 0.0)),
                    target_latitude=float(item.get("target_latitude", 0.0)),
                    target_type_code=item.get("target_type_code"),
                    enemy_friend_attr=item.get("enemy_friend_attr"),
                    military_civil_attr=item.get("military_civil_attr"),
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

    sync_mode = _resolve_target_sync_mode(data)
    if sync_mode == "replace":
        situation_store.replace_targets(models, revision=revision, source_id=source_id)
        return

    if not models and revision is None:
        return
    situation_store.update_targets(models, revision=revision, source_id=source_id)


def register_default_subscriptions(dds_adapter: DdsAdapter) -> None:
    dds_adapter.subscribe(OWNSHIP_NAVIGATION_TOPIC, _on_ownship_message)
    dds_adapter.subscribe(TARGET_PERCEPTION_TOPIC, _on_target_perception_message)
