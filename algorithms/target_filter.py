from math import atan2, cos, degrees, radians, sin
from typing import List, Optional, Tuple

from domain.models import GeoPoint, OwnShipState, TargetConstraint, TargetState, TaskArea
from utils.config_utils import (
    get_tracking_bearing_center_deg,
    get_tracking_bearing_window_deg,
    get_tracking_filter_identity_weights,
    get_tracking_hysteresis_margin,
    get_tracking_max_target_range_m,
    get_tracking_min_target_range_m,
    get_tracking_sector_center_deg,
    get_tracking_sector_width_deg,
    get_tracking_top_k_candidates,
    is_tracking_filter_debug_enabled,
    is_tracking_hysteresis_enabled,
    is_tracking_sector_filter_enabled,
)
from utils.geo_utils import haversine_distance_m, is_point_in_polygon


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
    if task_area is None:
        return True

    point = GeoPoint(longitude=target.longitude, latitude=target.latitude)
    return is_point_in_polygon(point, task_area.points)


def _has_explicit_identity_constraint(constraint: Optional[TargetConstraint]) -> bool:
    if constraint is None:
        return False
    return bool(constraint.target_id or constraint.target_batch_no is not None)


def _target_identity_hard_filter(target: TargetState, constraint: Optional[TargetConstraint]) -> bool:
    if constraint is None:
        return True

    if constraint.target_id and target.target_id != constraint.target_id:
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


def _preferred_bonus(value: Optional[int], preferred: Optional[List[int]], weight: float) -> float:
    if preferred and value in preferred:
        return weight
    return 0.0


def _target_identity_score(target: TargetState, constraint: Optional[TargetConstraint], weights: dict) -> float:
    if constraint is None:
        return 0.0

    score = 0.0
    if constraint.target_id and target.target_id == constraint.target_id:
        score += weights["target_id"]
    if constraint.target_batch_no is not None and target.target_batch_no == constraint.target_batch_no:
        score += weights["batch_id"]
    if constraint.target_type_code is not None and target.target_type_code == constraint.target_type_code:
        score += weights["target_type"]
    if constraint.enemy_friend_attr is not None and target.enemy_friend_attr == constraint.enemy_friend_attr:
        score += weights["enemy_friend"]
    if constraint.military_civil_attr is not None and target.military_civil_attr == constraint.military_civil_attr:
        score += weights["military_civil"]

    score += _preferred_bonus(
        value=target.target_type_code,
        preferred=constraint.preferred_target_type_codes,
        weight=weights["target_type_preferred"],
    )
    score += _preferred_bonus(
        value=target.enemy_friend_attr,
        preferred=constraint.preferred_enemy_friend_attrs,
        weight=weights["enemy_friend_preferred"],
    )
    score += _preferred_bonus(
        value=target.military_civil_attr,
        preferred=constraint.preferred_military_civil_attrs,
        weight=weights["military_civil_preferred"],
    )
    return score


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
) -> None:
    if not is_tracking_filter_debug_enabled():
        return

    print("\n[TargetFilter] candidate scores:")
    print(f"[TargetFilter] range_window: min={min_target_range_m:.2f} m, max={max_target_range_m:.2f} m")
    print(f"[TargetFilter] sector_skipped_for_identity: {sector_skipped_for_identity}")

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
            f'enemy_friend_attr={item["target"].enemy_friend_attr}, '
            f'military_civil_attr={item["target"].military_civil_attr}, '
            f'identity_score={item["identity_score"]:.3f}, '
            f'distance_score={item["distance_score"]:.3f}, '
            f'bearing_score={item["bearing_score"]:.3f}, '
            f'total_score={item["total_score"]:.3f}, '
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
            margin = get_tracking_hysteresis_margin()
            if top_candidate["target"].target_id != current_target_id:
                if top_candidate["total_score"] - current_item["total_score"] <= margin:
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
) -> Tuple[Optional[TargetState], List[dict]]:
    weights = get_tracking_filter_identity_weights()
    weights.update(identity_weights or {})

    min_range, max_range = _resolve_range_window(constraint)
    if max_target_range_m is not None:
        max_range = min(max_range, max_target_range_m)

    sector_skipped_for_identity = _has_explicit_identity_constraint(constraint)
    candidates = []

    for target in targets:
        if not target.active:
            continue
        if not _task_area_filter(target=target, task_area=task_area):
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

        bearing_passed, bearing_to_target_deg, relative_bearing_deg, bearing_score = _bearing_window_check(
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

        identity_score = _target_identity_score(target=target, constraint=constraint, weights=weights)
        total_score = identity_score + distance_score * weights["range"] + bearing_score * weights["bearing"]

        candidates.append(
            {
                "target": target,
                "identity_score": identity_score,
                "distance_score": distance_score,
                "bearing_score": bearing_score,
                "total_score": total_score,
                "distance_m": distance_m,
                "bearing_to_target_deg": bearing_to_target_deg,
                "relative_bearing_deg": relative_bearing_deg,
            }
        )

    candidates.sort(key=lambda item: item["total_score"], reverse=True)
    top_k_candidates = candidates[: get_tracking_top_k_candidates()]
    selected_target = _apply_hysteresis(candidates=top_k_candidates, current_target_id=current_target_id)

    _print_filter_debug(
        candidates=top_k_candidates,
        selected_target=selected_target,
        current_target_id=current_target_id,
        min_target_range_m=min_range,
        max_target_range_m=max_range,
        sector_skipped_for_identity=sector_skipped_for_identity,
    )

    debug_candidates = []
    for item in candidates:
        debug_candidates.append(
            {
                "target_id": item["target"].target_id,
                "target_name": item["target"].target_name,
                "target_type_code": item["target"].target_type_code,
                "target_batch_no": item["target"].target_batch_no,
                "enemy_friend_attr": item["target"].enemy_friend_attr,
                "military_civil_attr": item["target"].military_civil_attr,
                "identity_score": item["identity_score"],
                "distance_score": item["distance_score"],
                "bearing_score": item["bearing_score"],
                "total_score": item["total_score"],
                "distance_m": item["distance_m"],
                "bearing_to_target_deg": item["bearing_to_target_deg"],
                "relative_bearing_deg": item["relative_bearing_deg"],
            }
        )

    return selected_target, debug_candidates
