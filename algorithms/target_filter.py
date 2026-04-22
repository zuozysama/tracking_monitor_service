from math import atan2, cos, degrees, radians, sin
from typing import List, Optional, Tuple

from domain.models import GeoPoint, OwnShipState, TargetConstraint, TargetState, TaskArea
from utils.config_utils import (
    get_tracking_default_target_type_value_score,
    get_tracking_bearing_center_deg,
    get_tracking_bearing_window_deg,
    get_tracking_hysteresis_margin,
    get_tracking_max_target_range_m,
    get_tracking_min_target_range_m,
    get_tracking_sector_center_deg,
    get_tracking_sector_width_deg,
    get_tracking_target_type_value_scores,
    get_tracking_top_k_candidates,
    is_tracking_filter_debug_enabled,
    is_tracking_hysteresis_enabled,
    is_tracking_sector_filter_enabled,
)
from utils.geo_utils import haversine_distance_m
from utils.region_utils import is_target_in_task_area

DEFAULT_SURFACE_TARGET_POSITION_ATTR = 3
DEFAULT_MIN_THREAT_LEVEL = 2


def normalize_bearing_deg(angle: float) -> float:
    return angle % 360.0


def signed_angle_diff_deg(reference_deg: float, target_deg: float) -> float:
    return (target_deg - reference_deg + 180.0) % 360.0 - 180.0


def bearing_between_points_deg(start: GeoPoint, end: GeoPoint) -> float:
    lat1 = radians(start.latitude)
    lon1 = radians(start.longitude)
    lat2 = radians(end.latitude)
    lon2 = radians(end.longitude)

    dlon = lon2 - lon1
    x = sin(dlon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    bearing = degrees(atan2(x, y))
    return normalize_bearing_deg(bearing)


def _in_bearing_window(bearing_deg: float, min_deg: float, max_deg: float) -> bool:
    bearing_deg = normalize_bearing_deg(bearing_deg)
    min_deg = normalize_bearing_deg(min_deg)
    max_deg = normalize_bearing_deg(max_deg)
    if min_deg <= max_deg:
        return min_deg <= bearing_deg <= max_deg
    return bearing_deg >= min_deg or bearing_deg <= max_deg


def _task_area_filter(target: TargetState, task_area: Optional[TaskArea]) -> bool:
    return is_target_in_task_area(target=target, task_area=task_area)


def _has_explicit_identity_constraint(constraint: Optional[TargetConstraint]) -> bool:
    if constraint is None:
        return False
    return bool(constraint.target_id or constraint.target_batch_no is not None)


def _has_explicit_hard_constraint(constraint: Optional[TargetConstraint]) -> bool:
    if constraint is None:
        return False
    if _has_explicit_identity_constraint(constraint):
        return True

    if (
        constraint.target_type_code is not None
        or constraint.threat_level is not None
        or constraint.target_name not in {None, ""}
        or constraint.enemy_friend_attr is not None
        or constraint.military_civil_attr is not None
    ):
        return True

    if (
        constraint.allowed_target_type_codes
        or constraint.allowed_enemy_friend_attrs
        or constraint.allowed_military_civil_attrs
    ):
        return True

    if (
        constraint.min_target_range_m is not None
        or constraint.max_target_range_m is not None
        or constraint.bearing_min_deg is not None
        or constraint.bearing_max_deg is not None
    ):
        return True

    return False


def _should_apply_default_surface_filter(
    constraint: Optional[TargetConstraint],
    enabled: bool,
) -> bool:
    if not enabled:
        return False
    return not _has_explicit_hard_constraint(constraint)


def _default_surface_threat_filter(
    target: TargetState,
    required_position_attr: int,
    min_threat_level: int,
) -> bool:
    if target.target_position_attr != required_position_attr:
        return False
    return (target.threat_level or 0) >= min_threat_level


def _canonical_numeric_target_id(value: Optional[str]) -> Optional[int]:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    if text.isdigit():
        return int(text)
    prefix = "target-"
    if text.lower().startswith(prefix):
        suffix = text[len(prefix):]
        if suffix.isdigit():
            return int(suffix)
    return None


def _target_id_matches(target_id: Optional[str], constraint_target_id: Optional[str]) -> bool:
    if constraint_target_id in (None, ""):
        return True
    if target_id == constraint_target_id:
        return True

    target_num = _canonical_numeric_target_id(target_id)
    constraint_num = _canonical_numeric_target_id(constraint_target_id)
    if target_num is not None and constraint_num is not None:
        return target_num == constraint_num
    return False


def _target_identity_hard_filter(target: TargetState, constraint: Optional[TargetConstraint]) -> bool:
    if constraint is None:
        return True

    if constraint.target_id and not _target_id_matches(target.target_id, constraint.target_id):
        return False
    if constraint.target_batch_no is not None and target.target_batch_no != constraint.target_batch_no:
        return False
    return True


def _value_matches_allowed(value: Optional[int], allowed: Optional[List[int]]) -> bool:
    if not allowed:
        return True
    return value in allowed


def _target_attribute_hard_filter(target: TargetState, constraint: Optional[TargetConstraint]) -> bool:
    if constraint is None:
        return True

    if constraint.target_type_code is not None and target.target_type_code != constraint.target_type_code:
        return False
    if constraint.enemy_friend_attr is not None and target.enemy_friend_attr != constraint.enemy_friend_attr:
        return False
    if constraint.military_civil_attr is not None and target.military_civil_attr != constraint.military_civil_attr:
        return False

    if not _value_matches_allowed(target.target_type_code, constraint.allowed_target_type_codes):
        return False
    if not _value_matches_allowed(target.enemy_friend_attr, constraint.allowed_enemy_friend_attrs):
        return False
    if not _value_matches_allowed(target.military_civil_attr, constraint.allowed_military_civil_attrs):
        return False

    return True


def _target_value_score(target: TargetState) -> float:
    target_type_scores = get_tracking_target_type_value_scores()

    target_type_value = float(get_tracking_default_target_type_value_score())
    if target.target_type_code in target_type_scores:
        target_type_value = float(target_type_scores[target.target_type_code])

    return target_type_value


def _build_rank_key(
    threat_level: int,
    value_score: float,
    target_length_m: float,
    distance_m: Optional[float],
) -> Tuple[float, float, float, float]:
    # Ranking rule: threat(desc) -> value(desc) -> length(desc) -> distance(asc)
    distance_rank = distance_m if distance_m is not None else float("inf")
    return (
        -float(threat_level),
        -float(value_score),
        -float(target_length_m),
        float(distance_rank),
    )


def _resolve_range_window(constraint: Optional[TargetConstraint]) -> Tuple[float, float]:
    min_range = get_tracking_min_target_range_m()
    max_range = get_tracking_max_target_range_m()

    if constraint is not None:
        if constraint.min_target_range_m is not None:
            min_range = constraint.min_target_range_m
        if constraint.max_target_range_m is not None:
            max_range = constraint.max_target_range_m

    return min_range, max_range


def _distance_score(
    ownship: Optional[OwnShipState],
    target: TargetState,
    min_target_range_m: float,
    max_target_range_m: float,
) -> Tuple[float, Optional[float]]:
    if ownship is None:
        return 0.0, None

    ownship_point = GeoPoint(longitude=ownship.longitude, latitude=ownship.latitude)
    target_point = GeoPoint(longitude=target.longitude, latitude=target.latitude)
    distance_m = haversine_distance_m(ownship_point, target_point)

    if distance_m < min_target_range_m or distance_m > max_target_range_m:
        return float("-inf"), distance_m

    usable_span = max(max_target_range_m - min_target_range_m, 1e-6)
    normalized = 1.0 - ((distance_m - min_target_range_m) / usable_span)
    return max(0.0, min(1.0, normalized)), distance_m


def _bearing_window_check(
    ownship: Optional[OwnShipState],
    target: TargetState,
    constraint: Optional[TargetConstraint],
) -> Tuple[bool, Optional[float], Optional[float], float]:
    if ownship is None:
        return True, None, None, 0.0

    ownship_point = GeoPoint(longitude=ownship.longitude, latitude=ownship.latitude)
    target_point = GeoPoint(longitude=target.longitude, latitude=target.latitude)
    bearing_to_target_deg = bearing_between_points_deg(ownship_point, target_point)
    relative_bearing_deg = signed_angle_diff_deg(ownship.heading, bearing_to_target_deg)

    if constraint is not None and constraint.bearing_min_deg is not None and constraint.bearing_max_deg is not None:
        passed = _in_bearing_window(
            bearing_deg=bearing_to_target_deg,
            min_deg=constraint.bearing_min_deg,
            max_deg=constraint.bearing_max_deg,
        )
        if not passed:
            return False, bearing_to_target_deg, relative_bearing_deg, 0.0

        center_deg = normalize_bearing_deg((constraint.bearing_min_deg + constraint.bearing_max_deg) / 2.0)
        offset = abs(signed_angle_diff_deg(center_deg, bearing_to_target_deg))
        half_width = abs(signed_angle_diff_deg(center_deg, constraint.bearing_max_deg))
        if half_width <= 1e-6:
            return True, bearing_to_target_deg, relative_bearing_deg, 1.0
        return True, bearing_to_target_deg, relative_bearing_deg, max(0.0, 1.0 - (offset / half_width))

    window_deg = get_tracking_bearing_window_deg()
    if window_deg >= 360.0:
        return True, bearing_to_target_deg, relative_bearing_deg, 0.0

    center_deg = get_tracking_bearing_center_deg()
    half_width = window_deg / 2.0
    offset_to_center = abs(signed_angle_diff_deg(center_deg, relative_bearing_deg))
    passed = offset_to_center <= half_width
    if not passed:
        return False, bearing_to_target_deg, relative_bearing_deg, 0.0
    if half_width <= 1e-6:
        return True, bearing_to_target_deg, relative_bearing_deg, 1.0
    return True, bearing_to_target_deg, relative_bearing_deg, max(0.0, 1.0 - (offset_to_center / half_width))


def _sector_check(
    ownship: Optional[OwnShipState],
    target: TargetState,
    constraint: Optional[TargetConstraint],
) -> Tuple[bool, Optional[float], Optional[float]]:
    if _has_explicit_identity_constraint(constraint):
        return True, None, None
    if not is_tracking_sector_filter_enabled():
        return True, None, None
    if ownship is None:
        return True, None, None

    ownship_point = GeoPoint(longitude=ownship.longitude, latitude=ownship.latitude)
    target_point = GeoPoint(longitude=target.longitude, latitude=target.latitude)
    bearing_to_target_deg = bearing_between_points_deg(ownship_point, target_point)
    relative_bearing_deg = signed_angle_diff_deg(ownship.heading, bearing_to_target_deg)

    center_deg = get_tracking_sector_center_deg()
    width_deg = get_tracking_sector_width_deg()
    half_width = width_deg / 2.0
    offset_to_center = signed_angle_diff_deg(center_deg, relative_bearing_deg)
    passed = abs(offset_to_center) <= half_width
    return passed, bearing_to_target_deg, relative_bearing_deg


def _print_filter_debug(
    candidates: List[dict],
    selected_target: Optional[TargetState],
    current_target_id: Optional[str],
    min_target_range_m: float,
    max_target_range_m: float,
    sector_skipped_for_identity: bool,
    default_surface_filter_active: bool,
    default_surface_position_attr: int,
    default_min_threat_level: int,
) -> None:
    if not is_tracking_filter_debug_enabled():
        return

    print("\n[TargetFilter] candidate ranking:")
    print(f"[TargetFilter] range_window: min={min_target_range_m:.2f} m, max={max_target_range_m:.2f} m")
    print(f"[TargetFilter] sector_skipped_for_identity: {sector_skipped_for_identity}")
    print(
        f"[TargetFilter] default_surface_filter_active: {default_surface_filter_active} "
        f"(target_position_attr={default_surface_position_attr}, threat_level>={default_min_threat_level})"
    )

    if not candidates:
        print("[TargetFilter] no valid candidates")
        return

    print(f"[TargetFilter] current_target_id: {current_target_id}")
    for item in candidates:
        distance_text = "N/A" if item["distance_m"] is None else f'{item["distance_m"]:.2f} m'
        bearing_text = "N/A" if item["bearing_to_target_deg"] is None else f'{item["bearing_to_target_deg"]:.2f} deg'
        relative_bearing_text = "N/A" if item["relative_bearing_deg"] is None else f'{item["relative_bearing_deg"]:.2f} deg'
        print(
            f'  - target_id={item["target"].target_id}, '
            f'target_type_code={item["target"].target_type_code}, '
            f'target_position_attr={item["target"].target_position_attr}, '
            f'target_length_m={item["target"].target_length_m}, '
            f'enemy_friend_attr={item["target"].enemy_friend_attr}, '
            f'military_civil_attr={item["target"].military_civil_attr}, '
            f'threat_level={item["target"].threat_level}, '
            f'value_score={item["value_score"]:.3f}, '
            f'rank_key=(threat={item["rank_threat_level"]}, '
            f'value={item["rank_value_score"]:.3f}, '
            f'length={item["rank_target_length_m"]:.3f}, '
            f'distance={distance_text}), '
            f'distance={distance_text}, '
            f'bearing_to_target={bearing_text}, '
            f'relative_bearing={relative_bearing_text}'
        )

    if selected_target is not None:
        print(f"[TargetFilter] selected target: {selected_target.target_id}")
    else:
        print("[TargetFilter] selected target: None")


def _apply_hysteresis(candidates: List[dict], current_target_id: Optional[str]) -> Optional[TargetState]:
    if not candidates:
        return None

    top_candidate = candidates[0]
    selected_candidate = top_candidate
    if is_tracking_hysteresis_enabled() and current_target_id is not None and len(candidates) > 1:
        current_item = None
        for item in candidates:
            if item["target"].target_id == current_target_id:
                current_item = item
                break
        if current_item is not None:
            if top_candidate["target"].target_id != current_target_id:
                margin = max(float(get_tracking_hysteresis_margin()), 0.0)
                same_primary_key = (
                    top_candidate["rank_threat_level"] == current_item["rank_threat_level"]
                    and abs(top_candidate["rank_value_score"] - current_item["rank_value_score"]) <= 1e-6
                    and abs(top_candidate["rank_target_length_m"] - current_item["rank_target_length_m"]) <= 1e-6
                )
                top_distance = top_candidate["rank_distance_m"]
                current_distance = current_item["rank_distance_m"]
                # If only distance differs and improvement is small, keep current target.
                if same_primary_key and current_distance <= top_distance + margin:
                    selected_candidate = current_item
    return selected_candidate["target"]


def filter_and_select_target(
    targets: List[TargetState],
    ownship: Optional[OwnShipState],
    constraint: Optional[TargetConstraint],
    task_area: Optional[TaskArea],
    max_target_range_m: float,
    identity_weights: dict,
    current_target_id: Optional[str] = None,
    apply_default_surface_filter: bool = False,
    default_surface_position_attr: int = DEFAULT_SURFACE_TARGET_POSITION_ATTR,
    default_min_threat_level: int = DEFAULT_MIN_THREAT_LEVEL,
) -> Tuple[Optional[TargetState], List[dict]]:
    # Keep signature for compatibility; ranking no longer relies on legacy weighted total_score.
    _ = identity_weights

    min_range, max_range = _resolve_range_window(constraint)
    if max_target_range_m is not None:
        max_range = min(max_range, max_target_range_m)

    default_surface_filter_active = _should_apply_default_surface_filter(
        constraint=constraint,
        enabled=apply_default_surface_filter,
    )
    sector_skipped_for_identity = _has_explicit_identity_constraint(constraint)
    candidates = []

    for target in targets:
        if not target.active:
            continue
        if not _task_area_filter(target=target, task_area=task_area):
            continue
        if default_surface_filter_active and not _default_surface_threat_filter(
            target=target,
            required_position_attr=default_surface_position_attr,
            min_threat_level=default_min_threat_level,
        ):
            continue
        if not _target_identity_hard_filter(target=target, constraint=constraint):
            continue
        if not _target_attribute_hard_filter(target=target, constraint=constraint):
            continue

        sector_passed, sector_bearing_deg, sector_relative_bearing_deg = _sector_check(
            ownship=ownship,
            target=target,
            constraint=constraint,
        )
        if not sector_passed:
            continue

        bearing_passed, bearing_to_target_deg, relative_bearing_deg, _bearing_score = _bearing_window_check(
            ownship=ownship,
            target=target,
            constraint=constraint,
        )
        if not bearing_passed:
            continue

        distance_score, distance_m = _distance_score(
            ownship=ownship,
            target=target,
            min_target_range_m=min_range,
            max_target_range_m=max_range,
        )
        if distance_score == float("-inf"):
            continue

        if bearing_to_target_deg is None:
            bearing_to_target_deg = sector_bearing_deg
        if relative_bearing_deg is None:
            relative_bearing_deg = sector_relative_bearing_deg

        threat_level = int(target.threat_level or 0)
        value_score = _target_value_score(target=target)
        target_length_m = float(target.target_length_m or 0.0)
        rank_key = _build_rank_key(
            threat_level=threat_level,
            value_score=value_score,
            target_length_m=target_length_m,
            distance_m=distance_m,
        )

        candidates.append(
            {
                "target": target,
                "value_score": value_score,
                "distance_m": distance_m,
                "bearing_to_target_deg": bearing_to_target_deg,
                "relative_bearing_deg": relative_bearing_deg,
                "rank_threat_level": threat_level,
                "rank_value_score": value_score,
                "rank_target_length_m": target_length_m,
                "rank_distance_m": distance_m if distance_m is not None else float("inf"),
                "rank_key": rank_key,
            }
        )

    # Unified ordering for both auto selection and manual-switch baseline:
    # threat(desc) -> value(desc) -> length(desc) -> distance(asc)
    candidates.sort(key=lambda item: item["rank_key"])
    top_k_candidates = candidates[: get_tracking_top_k_candidates()]
    selected_target = _apply_hysteresis(candidates=top_k_candidates, current_target_id=current_target_id)

    _print_filter_debug(
        candidates=top_k_candidates,
        selected_target=selected_target,
        current_target_id=current_target_id,
        min_target_range_m=min_range,
        max_target_range_m=max_range,
        sector_skipped_for_identity=sector_skipped_for_identity,
        default_surface_filter_active=default_surface_filter_active,
        default_surface_position_attr=default_surface_position_attr,
        default_min_threat_level=default_min_threat_level,
    )

    debug_candidates = []
    for item in candidates:
        rank_distance_m = item["distance_m"] if item["distance_m"] is not None else None
        debug_candidates.append(
            {
                "target_id": item["target"].target_id,
                "target_name": item["target"].target_name,
                "target_type_code": item["target"].target_type_code,
                "target_position_attr": item["target"].target_position_attr,
                "target_length_m": item["target"].target_length_m,
                "target_batch_no": item["target"].target_batch_no,
                "threat_level": item["target"].threat_level,
                "enemy_friend_attr": item["target"].enemy_friend_attr,
                "military_civil_attr": item["target"].military_civil_attr,
                "value_score": item["value_score"],
                "rank_threat_level": item["rank_threat_level"],
                "rank_value_score": item["rank_value_score"],
                "rank_target_length_m": item["rank_target_length_m"],
                "rank_distance_m": rank_distance_m,
                "sort_key": {
                    "threat_level_desc": item["rank_threat_level"],
                    "value_score_desc": item["rank_value_score"],
                    "target_length_m_desc": item["rank_target_length_m"],
                    "distance_m_asc": rank_distance_m,
                },
                "distance_m": item["distance_m"],
                "bearing_to_target_deg": item["bearing_to_target_deg"],
                "relative_bearing_deg": item["relative_bearing_deg"],
            }
        )

    return selected_target, debug_candidates
