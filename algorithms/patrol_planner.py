import math
from dataclasses import dataclass
from typing import List, Tuple

from domain.models import GeoPoint, PatrolWaypoint, TaskArea


EARTH_RADIUS_M = 6371000.0


@dataclass
class _LocalPoint:
    x: float
    y: float


def _normalize_pass_count(num_passes: int) -> int:
    return max(2, num_passes)


def _project_to_local(points: List[GeoPoint]) -> Tuple[List[_LocalPoint], float, float]:
    ref_lat = sum(point.latitude for point in points) / len(points)
    ref_lon = sum(point.longitude for point in points) / len(points)
    ref_lat_rad = math.radians(ref_lat)

    projected = []
    for point in points:
        x = math.radians(point.longitude - ref_lon) * EARTH_RADIUS_M * math.cos(ref_lat_rad)
        y = math.radians(point.latitude - ref_lat) * EARTH_RADIUS_M
        projected.append(_LocalPoint(x=x, y=y))

    return projected, ref_lon, ref_lat


def _project_from_local(point: _LocalPoint, ref_lon: float, ref_lat: float) -> GeoPoint:
    ref_lat_rad = math.radians(ref_lat)
    longitude = ref_lon + math.degrees(point.x / (EARTH_RADIUS_M * max(math.cos(ref_lat_rad), 1e-12)))
    latitude = ref_lat + math.degrees(point.y / EARTH_RADIUS_M)
    return GeoPoint(longitude=longitude, latitude=latitude)


def _distance_m(dx: float, dy: float) -> float:
    return math.hypot(dx, dy)


def _rotate_xy(x: float, y: float, angle_deg: float) -> Tuple[float, float]:
    rad = math.radians(angle_deg)
    c = math.cos(rad)
    s = math.sin(rad)
    return x * c - y * s, x * s + y * c


def _dedupe_path_points(points: List[Tuple[float, float]], eps: float = 1e-6) -> List[Tuple[float, float]]:
    cleaned: List[Tuple[float, float]] = []
    for x, y in points:
        if not cleaned or _distance_m(x - cleaned[-1][0], y - cleaned[-1][1]) > eps:
            cleaned.append((x, y))
    return cleaned


def _point_on_segment(
    px: float,
    py: float,
    ax: float,
    ay: float,
    bx: float,
    by: float,
    eps: float = 1e-6,
) -> bool:
    cross = (px - ax) * (by - ay) - (py - ay) * (bx - ax)
    if abs(cross) > eps:
        return False
    return min(ax, bx) - eps <= px <= max(ax, bx) + eps and min(ay, by) - eps <= py <= max(ay, by) + eps


def _point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]], eps: float = 1e-6) -> bool:
    px, py = point
    inside = False
    n = len(polygon)
    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]
        if _point_on_segment(px, py, x1, y1, x2, y2, eps=eps):
            return True
        intersects = (y1 > py) != (y2 > py)
        if intersects:
            x_cross = x1 + (py - y1) * (x2 - x1) / (y2 - y1)
            if x_cross >= px - eps:
                inside = not inside
    return inside


def _scanline_intervals(rotated_polygon: List[Tuple[float, float]], y_scan: float, eps: float = 1e-6) -> List[Tuple[float, float]]:
    xs: List[float] = []
    n = len(rotated_polygon)
    for i in range(n):
        x1, y1 = rotated_polygon[i]
        x2, y2 = rotated_polygon[(i + 1) % n]
        if abs(y2 - y1) <= eps:
            continue
        ymin = min(y1, y2)
        ymax = max(y1, y2)
        if y_scan < ymin - eps or y_scan >= ymax - eps:
            continue
        x = x1 + (y_scan - y1) * (x2 - x1) / (y2 - y1)
        xs.append(x)

    xs.sort()
    merged: List[float] = []
    for x in xs:
        if not merged or abs(x - merged[-1]) > eps:
            merged.append(x)

    intervals: List[Tuple[float, float]] = []
    for i in range(0, len(merged) - 1, 2):
        x1 = merged[i]
        x2 = merged[i + 1]
        if x2 - x1 > eps:
            intervals.append((x1, x2))
    return intervals


def _build_scan_positions(min_y: float, max_y: float, search_radius: float, spacing: float) -> List[float]:
    span = max_y - min_y
    if span <= 2.0 * search_radius + 1e-6:
        return [(min_y + max_y) / 2.0]

    start = min_y + search_radius
    end = max_y - search_radius
    if start > end:
        return [(min_y + max_y) / 2.0]

    ys = [start]
    while ys[-1] + spacing < end - 1e-6:
        ys.append(ys[-1] + spacing)
    if end - ys[-1] > 1e-6:
        ys.append(end)
    return ys


def _estimate_scan_count(min_y: float, max_y: float, search_radius: float, spacing: float) -> int:
    return len(_build_scan_positions(min_y, max_y, search_radius, spacing))


def _choose_sweep_angle(polygon: List[Tuple[float, float]], search_radius: float, spacing: float) -> float:
    candidates = [0.0]
    for i in range(len(polygon)):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % len(polygon)]
        if _distance_m(x2 - x1, y2 - y1) <= 1e-6:
            continue
        angle = math.degrees(math.atan2(y2 - y1, x2 - x1)) % 180.0
        if all(abs(angle - existing) > 1e-6 for existing in candidates):
            candidates.append(angle)

    best_angle = 0.0
    best_score = None
    for angle in candidates:
        rotated = [_rotate_xy(x, y, -angle) for x, y in polygon]
        xs = [point[0] for point in rotated]
        ys = [point[1] for point in rotated]
        span_x = max(xs) - min(xs)
        scan_count = _estimate_scan_count(min(ys), max(ys), search_radius, spacing)
        path_proxy = scan_count * span_x + max(0, scan_count - 1) * spacing
        score = (scan_count, path_proxy, angle)
        if best_score is None or score < best_score:
            best_score = score
            best_angle = angle
    return best_angle


def _build_coverage_path(
    polygon: List[Tuple[float, float]],
    sweep_angle_deg: float,
    search_radius: float,
    spacing: float,
    boundary_clearance: float,
) -> List[_LocalPoint]:
    rotated = [_rotate_xy(x, y, -sweep_angle_deg) for x, y in polygon]
    ys = [point[1] for point in rotated]
    scan_positions = _build_scan_positions(min(ys), max(ys), search_radius, spacing)

    raw_points: List[Tuple[float, float]] = []
    left_to_right = True
    for y_scan in scan_positions:
        intervals = _scanline_intervals(rotated, y_scan)
        if not intervals:
            continue

        if left_to_right:
            ordered = [(x1, x2) for x1, x2 in intervals]
        else:
            ordered = [(x2, x1) for x1, x2 in reversed(intervals)]

        for x_start, x_end in ordered:
            if x_end >= x_start:
                inner_start = x_start + boundary_clearance
                inner_end = x_end - boundary_clearance
            else:
                inner_start = x_start - boundary_clearance
                inner_end = x_end + boundary_clearance

            if abs(inner_end - inner_start) <= 1e-6:
                continue
            if x_end >= x_start and inner_end <= inner_start:
                continue
            if x_end < x_start and inner_end >= inner_start:
                continue

            raw_points.append(_rotate_xy(inner_start, y_scan, sweep_angle_deg))
            raw_points.append(_rotate_xy(inner_end, y_scan, sweep_angle_deg))

        left_to_right = not left_to_right

    waypoints = []
    for x, y in _dedupe_path_points(raw_points):
        if _point_in_polygon((x, y), polygon):
            waypoints.append(_LocalPoint(x=x, y=y))
    return waypoints


def _densify_path(points: List[_LocalPoint], max_step_m: float) -> List[_LocalPoint]:
    if len(points) <= 1 or max_step_m <= 1e-6:
        return list(points)

    dense = [points[0]]
    for idx in range(len(points) - 1):
        start = points[idx]
        end = points[idx + 1]
        dx = end.x - start.x
        dy = end.y - start.y
        dist = _distance_m(dx, dy)
        if dist > max_step_m:
            steps = int(math.ceil(dist / max_step_m))
            for step in range(1, steps):
                ratio = step / steps
                dense.append(_LocalPoint(x=start.x + dx * ratio, y=start.y + dy * ratio))
        dense.append(end)
    return dense


def generate_simple_patrol_waypoints(
    task_area: TaskArea,
    expected_speed: float,
    num_passes: int = 4,
) -> List[PatrolWaypoint]:
    if task_area.area_type == "route":
        return [
            PatrolWaypoint(
                longitude=point.longitude,
                latitude=point.latitude,
                expected_speed=expected_speed,
            )
            for point in task_area.points
        ]

    pass_count = _normalize_pass_count(num_passes)
    local_polygon, ref_lon, ref_lat = _project_to_local(task_area.points)
    polygon_xy = [(point.x, point.y) for point in local_polygon]

    xs = [point.x for point in local_polygon]
    ys = [point.y for point in local_polygon]
    span_y = max(ys) - min(ys)
    spacing = max(span_y / max(pass_count - 1, 1), 1.0)
    search_radius = spacing / 2.0
    boundary_clearance = min(max(spacing * 0.05, 0.0), 5.0)

    sweep_angle_deg = _choose_sweep_angle(
        polygon=polygon_xy,
        search_radius=search_radius,
        spacing=spacing,
    )
    local_waypoints = _build_coverage_path(
        polygon=polygon_xy,
        sweep_angle_deg=sweep_angle_deg,
        search_radius=search_radius,
        spacing=spacing,
        boundary_clearance=boundary_clearance,
    )

    if not local_waypoints:
        centroid = GeoPoint(longitude=ref_lon, latitude=ref_lat)
        return [
            PatrolWaypoint(
                longitude=centroid.longitude,
                latitude=centroid.latitude,
                expected_speed=expected_speed,
            )
        ]

    dense_waypoints = _densify_path(local_waypoints, max_step_m=max(spacing, 1.0))
    return [
        PatrolWaypoint(
            longitude=geo_point.longitude,
            latitude=geo_point.latitude,
            expected_speed=expected_speed,
        )
        for geo_point in (
            _project_from_local(point, ref_lon=ref_lon, ref_lat=ref_lat)
            for point in dense_waypoints
        )
    ]
