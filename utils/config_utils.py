from __future__ import annotations

import os

from config.settings import settings


def _get_env_int(name: str, default: int, min_value: int | None = None) -> int:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = int(raw)
    except Exception:
        return default
    if min_value is not None and value < min_value:
        return default
    return value


def _get_env_float(name: str, default: float, min_value: float | None = None) -> float:
    raw = os.getenv(name, str(default)).strip()
    try:
        value = float(raw)
    except Exception:
        return default
    if min_value is not None and value < min_value:
        return default
    return value


def _get_env_optional_float(name: str, min_value: float | None = None) -> float | None:
    raw = os.getenv(name)
    if raw is None:
        return None
    text = raw.strip()
    if not text:
        return None
    try:
        value = float(text)
    except Exception:
        return None
    if min_value is not None and value < min_value:
        return None
    return value


def get_fixed_tracking_default_radius_m() -> float:
    return settings.fixed_tracking.default_region_radius_m


def get_tracking_default_target_lost_timeout_sec() -> float:
    return settings.tracking.target_lost_timeout_sec


def get_tracking_escort_distance_m() -> float:
    return _get_env_float(
        "TRACKING_ESCORT_DISTANCE_M",
        float(settings.tracking.escort_distance_m),
        min_value=0.0,
    )


def get_tracking_intercept_distance_m() -> float:
    return _get_env_float(
        "TRACKING_INTERCEPT_DISTANCE_M",
        float(settings.tracking.intercept_distance_m),
        min_value=0.0,
    )


def get_tracking_expel_distance_m() -> float:
    return _get_env_float(
        "TRACKING_EXPEL_DISTANCE_M",
        float(settings.tracking.expel_distance_m),
        min_value=0.0,
    )


def get_tracking_manual_selection_timeout_sec() -> int:
    return int(settings.tracking.manual_selection_timeout_sec)


def get_tracking_manual_switch_timeout_sec() -> int:
    return int(settings.tracking.manual_switch_timeout_sec)


def get_tracking_min_target_range_m() -> float:
    return settings.tracking.filter.min_target_range_m


def get_tracking_max_target_range_m() -> float:
    return settings.tracking.filter.max_target_range_m


def get_tracking_filter_identity_weights() -> dict:
    return {
        "target_id": settings.tracking.filter.target_id_weight,
        "batch_id": settings.tracking.filter.batch_id_weight,
        "target_type": settings.tracking.filter.target_type_weight,
        "target_type_preferred": settings.tracking.filter.target_type_preferred_weight,
        "enemy_friend": settings.tracking.filter.enemy_friend_weight,
        "enemy_friend_preferred": settings.tracking.filter.enemy_friend_preferred_weight,
        "military_civil": settings.tracking.filter.military_civil_weight,
        "military_civil_preferred": settings.tracking.filter.military_civil_preferred_weight,
        "range": settings.tracking.filter.range_score_weight,
        "bearing": settings.tracking.filter.bearing_score_weight,
        "threat": settings.tracking.filter.threat_score_weight,
        "value": settings.tracking.filter.value_score_weight,
    }


def is_tracking_filter_debug_enabled() -> bool:
    return settings.tracking.filter.debug_enabled


def is_tracking_sector_filter_enabled() -> bool:
    return settings.tracking.filter.sector_filter_enabled


def get_tracking_sector_center_deg() -> float:
    return settings.tracking.filter.sector_center_deg


def get_tracking_sector_width_deg() -> float:
    return settings.tracking.filter.sector_width_deg


def get_tracking_bearing_center_deg() -> float:
    return settings.tracking.filter.bearing_center_deg


def get_tracking_bearing_window_deg() -> float:
    return settings.tracking.filter.bearing_window_deg


def get_tracking_top_k_candidates() -> int:
    return settings.tracking.filter.top_k_candidates


def is_tracking_hysteresis_enabled() -> bool:
    return settings.tracking.filter.hysteresis_enabled


def get_tracking_hysteresis_margin() -> float:
    return settings.tracking.filter.hysteresis_margin


def get_tracking_threat_level_max() -> float:
    return settings.tracking.filter.threat_level_max


def get_tracking_default_min_threat_level() -> int:
    return int(settings.tracking.filter.default_min_threat_level)


def get_tracking_default_target_type_value_score() -> float:
    return settings.tracking.filter.default_target_type_value_score


def get_tracking_default_military_civil_value_score() -> float:
    return settings.tracking.filter.default_military_civil_value_score


def get_tracking_target_type_value_scores() -> dict:
    return settings.tracking.filter.target_type_value_scores


def get_tracking_military_civil_value_scores() -> dict:
    return settings.tracking.filter.military_civil_value_scores


def get_tracking_arrival_tolerance_m() -> float:
    return settings.tracking.arrival.tolerance_m


def get_tracking_arrival_stable_cycles() -> int:
    return settings.tracking.arrival.stable_cycles


def get_tracking_arrival_heading_tolerance_deg() -> float:
    return settings.tracking.arrival.heading_tolerance_deg


def get_tracking_arrival_speed_tolerance_kn() -> float:
    return settings.tracking.arrival.speed_tolerance_kn


def get_optical_post_retry_interval_sec() -> int:
    return settings.collaboration.optical_post_retry_interval_sec


def get_sonar_poll_interval_sec() -> int:
    return settings.collaboration.sonar_poll_interval_sec


def get_dds_focus_platform_id() -> int:
    raw = os.getenv("DDS_FOCUS_PLATFORM_ID", "1001").strip()
    try:
        return int(raw)
    except Exception:
        return 1001


def get_dds_target_stale_timeout_sec() -> float:
    raw = os.getenv("DDS_TARGET_STALE_TIMEOUT_SEC", "3.0").strip()
    try:
        value = float(raw)
    except Exception:
        return 3.0
    if value <= 0:
        return 3.0
    return value


def get_patrol_num_passes() -> int:
    return _get_env_int("PATROL_NUM_PASSES", 4, min_value=2)


def get_patrol_scan_radius_m() -> float | None:
    value = _get_env_optional_float("PATROL_SCAN_RADIUS_M", min_value=0.1)
    if value is None:
        return 500.0
    return value


def get_patrol_boundary_clearance_m() -> float | None:
    value = _get_env_optional_float("PATROL_BOUNDARY_CLEARANCE_M", min_value=0.0)
    if value is None:
        return 500.0
    return value
