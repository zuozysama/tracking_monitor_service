from math import asin, atan2, cos, degrees, radians, sin
from typing import Optional

from domain.enums import TrackingMode
from domain.models import GeoPoint, OwnShipState, TargetState
from utils.geo_utils import haversine_distance_m


EARTH_RADIUS_M = 6371000.0


def normalize_bearing_deg(angle: float) -> float:
    return angle % 360.0


def move_point_by_bearing_and_distance(
    start: GeoPoint,
    bearing_deg: float,
    distance_m: float,
) -> GeoPoint:
    bearing = radians(bearing_deg)
    lat1 = radians(start.latitude)
    lon1 = radians(start.longitude)

    angular_distance = distance_m / EARTH_RADIUS_M

    lat2 = asin(
        sin(lat1) * cos(angular_distance)
        + cos(lat1) * sin(angular_distance) * cos(bearing)
    )

    lon2 = lon1 + atan2(
        sin(bearing) * sin(angular_distance) * cos(lat1),
        cos(angular_distance) - sin(lat1) * sin(lat2),
    )

    return GeoPoint(
        longitude=degrees(lon2),
        latitude=degrees(lat2),
    )


def bearing_between_points_deg(start: GeoPoint, end: GeoPoint) -> float:
    lat1 = radians(start.latitude)
    lon1 = radians(start.longitude)
    lat2 = radians(end.latitude)
    lon2 = radians(end.longitude)

    dlon = lon2 - lon1
    x = sin(dlon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(dlon)
    return normalize_bearing_deg(degrees(atan2(x, y)))


def relative_signed_angle_deg(reference_deg: float, target_deg: float) -> float:
    return (target_deg - reference_deg + 180.0) % 360.0 - 180.0


def _min_turn_deg(current_heading_deg: float, desired_bearing_deg: float) -> float:
    current = normalize_bearing_deg(current_heading_deg)
    desired = normalize_bearing_deg(desired_bearing_deg)
    diff = abs(current - desired)
    return min(diff, 360.0 - diff)


def _normalize_weights(sector_weights: dict[str, float], sectors: list[str]) -> dict[str, float]:
    weights = {sector: max(float(sector_weights.get(sector, 0.0)), 0.0) for sector in sectors}
    total = sum(weights.values())
    if total <= 1e-9:
        avg = 1.0 / max(len(sectors), 1)
        return {sector: avg for sector in sectors}
    return {sector: weights[sector] / total for sector in sectors}


def _sector_to_bearing_offset(sector: str) -> float:
    mapping = {
        "front": 0.0,
        "rear": 180.0,
        "left": -90.0,
        "right": 90.0,
        "left_rear": 225.0,
        "right_rear": 135.0,
        "left_front": 315.0,
        "right_front": 45.0,
    }
    return mapping.get(sector, 180.0)


def _default_mode_sector_weights(
    mode: TrackingMode,
    target: TargetState,
    ownship: Optional[OwnShipState],
) -> tuple[list[str], dict[str, float], float]:
    if mode == TrackingMode.INTERCEPT:
        return ["front", "left", "right"], {"front": 1.0, "left": 0.6, "right": 0.6}, 1.0

    if mode == TrackingMode.EXPEL:
        if ownship is None:
            return ["left", "right"], {"left": 1.0, "right": 0.9}, 1.0

        target_point = GeoPoint(longitude=target.longitude, latitude=target.latitude)
        ownship_point = GeoPoint(longitude=ownship.longitude, latitude=ownship.latitude)
        bearing_target_to_ownship = bearing_between_points_deg(target_point, ownship_point)
        signed_angle = relative_signed_angle_deg(target.heading, bearing_target_to_ownship)
        if signed_angle > 0:
            return ["right", "left"], {"right": 1.0, "left": 0.6}, 1.0
        return ["left", "right"], {"left": 1.0, "right": 0.6}, 1.0

    return ["rear", "left_rear", "right_rear"], {"rear": 1.0, "left_rear": 0.75, "right_rear": 0.75}, 1.0


def generate_tracking_candidate_points(
    mode: TrackingMode,
    target: TargetState,
    ownship: Optional[OwnShipState],
    escort_distance_m: float,
    intercept_distance_m: float,
    expel_distance_m: float,
    alpha_sector: float = 1.0,
    beta_maneuver: float = 1.0,
    w_dist: float = 0.7,
    w_turn: float = 0.3,
    intercept_stage: int = 0,
    intercept_side: Optional[str] = None,
    expel_stage: int = 0,
    expel_side: Optional[str] = None,
) -> list[dict]:
    if mode == TrackingMode.INTERCEPT:
        follow_distance_m = intercept_distance_m
    elif mode == TrackingMode.EXPEL:
        follow_distance_m = escort_distance_m if expel_stage <= 0 else expel_distance_m
    else:
        follow_distance_m = escort_distance_m

    if mode == TrackingMode.INTERCEPT and intercept_stage <= 0:
        sectors = ["rear", "left_rear", "right_rear"]
        sector_weights = {"rear": 1.0, "left_rear": 0.75, "right_rear": 0.75}
        bearing_resolution_deg = 1.0
    elif mode == TrackingMode.INTERCEPT and intercept_stage == 1:
        if intercept_side == "right":
            sectors = ["right"]
            sector_weights = {"right": 1.0}
        elif intercept_side == "left":
            sectors = ["left"]
            sector_weights = {"left": 1.0}
        else:
            sectors = ["left", "right"]
            sector_weights = {"left": 1.0, "right": 1.0}
        bearing_resolution_deg = 1.0
    elif mode == TrackingMode.INTERCEPT:
        if intercept_side == "right":
            sectors = ["right_front"]
            sector_weights = {"right_front": 1.0}
        elif intercept_side == "left":
            sectors = ["left_front"]
            sector_weights = {"left_front": 1.0}
        else:
            sectors = ["left_front", "right_front"]
            sector_weights = {"left_front": 1.0, "right_front": 1.0}
        bearing_resolution_deg = 1.0
    elif mode == TrackingMode.EXPEL and expel_stage <= 0:
        sectors = ["rear", "left_rear", "right_rear"]
        sector_weights = {"rear": 1.0, "left_rear": 0.75, "right_rear": 0.75}
        bearing_resolution_deg = 1.0
    elif mode == TrackingMode.EXPEL:
        if expel_side == "right":
            sectors = ["right"]
            sector_weights = {"right": 1.0}
        elif expel_side == "left":
            sectors = ["left"]
            sector_weights = {"left": 1.0}
        else:
            sectors = ["left", "right"]
            sector_weights = {"left": 1.0, "right": 1.0}
        bearing_resolution_deg = 1.0
    else:
        sectors, sector_weights, bearing_resolution_deg = _default_mode_sector_weights(
            mode=mode,
            target=target,
            ownship=ownship,
        )
    norm_weights = _normalize_weights(sector_weights, sectors)

    target_point = GeoPoint(longitude=target.longitude, latitude=target.latitude)
    target_heading = normalize_bearing_deg(target.heading)
    candidates: list[dict] = []

    for sector in sectors:
        abs_bearing = normalize_bearing_deg(target_heading + _sector_to_bearing_offset(sector))
        if bearing_resolution_deg > 1e-6:
            abs_bearing = round(abs_bearing / bearing_resolution_deg) * bearing_resolution_deg
            abs_bearing = normalize_bearing_deg(abs_bearing)

        point = move_point_by_bearing_and_distance(
            start=target_point,
            bearing_deg=abs_bearing,
            distance_m=follow_distance_m,
        )

        dist_from_own_m = 0.0
        turn_cost_deg = 0.0
        if ownship is not None:
            ownship_point = GeoPoint(longitude=ownship.longitude, latitude=ownship.latitude)
            dist_from_own_m = haversine_distance_m(ownship_point, point)
            desired_bearing_deg = bearing_between_points_deg(ownship_point, point)
            turn_cost_deg = _min_turn_deg(ownship.heading, desired_bearing_deg)

        candidates.append(
            {
                "sector": sector,
                "point": point,
                "rel_range_m": follow_distance_m,
                "rel_bearing_deg": abs_bearing,
                "sector_weight": norm_weights.get(sector, 0.0),
                "dist_from_own_m": dist_from_own_m,
                "turn_cost_deg": turn_cost_deg,
                "maneuver_cost": 0.0,
                "point_score": 0.0,
            }
        )

    if not candidates:
        return candidates

    dists = [candidate["dist_from_own_m"] for candidate in candidates]
    turns = [candidate["turn_cost_deg"] for candidate in candidates]
    dmin, dmax = min(dists), max(dists)
    tmin, tmax = min(turns), max(turns)

    def _norm01(value: float, min_value: float, max_value: float) -> float:
        if max_value - min_value < 1e-9:
            return 0.0
        return (value - min_value) / (max_value - min_value)

    for candidate in candidates:
        nd = _norm01(candidate["dist_from_own_m"], dmin, dmax)
        nt = _norm01(candidate["turn_cost_deg"], tmin, tmax)
        candidate["maneuver_cost"] = w_dist * nd + w_turn * nt
        candidate["point_score"] = alpha_sector * candidate["sector_weight"] - beta_maneuver * candidate["maneuver_cost"]

    candidates.sort(key=lambda item: item["point_score"], reverse=True)
    return candidates


def pick_best_tracking_candidate(candidates: list[dict]) -> Optional[dict]:
    if not candidates:
        return None
    return candidates[0]


def generate_simple_tracking_point(
    mode: TrackingMode,
    target: TargetState,
    ownship: Optional[OwnShipState],
    escort_distance_m: float,
    intercept_distance_m: float,
    expel_distance_m: float,
    intercept_stage: int = 0,
    intercept_side: Optional[str] = None,
    expel_stage: int = 0,
    expel_side: Optional[str] = None,
) -> tuple[GeoPoint, float]:
    candidates = generate_tracking_candidate_points(
        mode=mode,
        target=target,
        ownship=ownship,
        escort_distance_m=escort_distance_m,
        intercept_distance_m=intercept_distance_m,
        expel_distance_m=expel_distance_m,
        intercept_stage=intercept_stage,
        intercept_side=intercept_side,
        expel_stage=expel_stage,
        expel_side=expel_side,
    )
    best_candidate = pick_best_tracking_candidate(candidates)
    if best_candidate is not None:
        return best_candidate["point"], best_candidate["rel_bearing_deg"]

    target_point = GeoPoint(longitude=target.longitude, latitude=target.latitude)
    fallback_bearing = normalize_bearing_deg(target.heading + 180.0)
    fallback_point = move_point_by_bearing_and_distance(
        start=target_point,
        bearing_deg=fallback_bearing,
        distance_m=escort_distance_m,
    )
    return fallback_point, fallback_bearing
