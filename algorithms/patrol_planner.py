import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from domain.models import GeoPoint, PatrolWaypoint, TaskArea


EARTH_RADIUS_M = 6371000.0
START_POINT_MIN_GAP_M = 10.0


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


def _project_point_to_local(point: GeoPoint, ref_lon: float, ref_lat: float) -> _LocalPoint:
    ref_lat_rad = math.radians(ref_lat)
    return _LocalPoint(
        x=math.radians(point.longitude - ref_lon) * EARTH_RADIUS_M * math.cos(ref_lat_rad),
        y=math.radians(point.latitude - ref_lat) * EARTH_RADIUS_M,
    )


def _project_from_local(point: _LocalPoint, ref_lon: float, ref_lat: float) -> GeoPoint:
    ref_lat_rad = math.radians(ref_lat)
    longitude = ref_lon + math.degrees(point.x / (EARTH_RADIUS_M * max(math.cos(ref_lat_rad), 1e-12)))
    latitude = ref_lat + math.degrees(point.y / EARTH_RADIUS_M)
    return GeoPoint(longitude=longitude, latitude=latitude)


def _distance_m(dx: float, dy: float) -> float:
    return math.hypot(dx, dy)


def _haversine_distance_m(a: GeoPoint, b: GeoPoint) -> float:
    lat1 = math.radians(a.latitude)
    lat2 = math.radians(b.latitude)
    dlat = lat2 - lat1
    dlon = math.radians(b.longitude - a.longitude)
    sin_dlat = math.sin(dlat / 2.0)
    sin_dlon = math.sin(dlon / 2.0)
    h = sin_dlat * sin_dlat + math.cos(lat1) * math.cos(lat2) * sin_dlon * sin_dlon
    return 2.0 * EARTH_RADIUS_M * math.atan2(math.sqrt(h), math.sqrt(max(1e-12, 1.0 - h)))


def _wrap_360(deg: float) -> float:
    wrapped = deg % 360.0
    if wrapped < 0:
        wrapped += 360.0
    return wrapped


def _min_turn_deg(current_heading_deg: float, desired_heading_deg: float) -> float:
    a = _wrap_360(current_heading_deg)
    b = _wrap_360(desired_heading_deg)
    diff = abs(a - b)
    return min(diff, 360.0 - diff)


def _bearing_from_vector(dx: float, dy: float) -> float:
    # Local x-axis points east, y-axis points north.
    return _wrap_360(math.degrees(math.atan2(dx, dy)))


def _build_circle_waypoints(
    center: GeoPoint,
    radius_m: float,
    expected_speed: float,
    num_points: int = 12,
) -> List[PatrolWaypoint]:
    count = max(8, num_points)
    lat_rad = math.radians(center.latitude)
    cos_lat = max(math.cos(lat_rad), 1e-12)

    waypoints: List[PatrolWaypoint] = []
    for idx in range(count):
        angle = 2.0 * math.pi * idx / count
        dx = radius_m * math.cos(angle)
        dy = radius_m * math.sin(angle)
        lon = center.longitude + math.degrees(dx / (EARTH_RADIUS_M * cos_lat))
        lat = center.latitude + math.degrees(dy / EARTH_RADIUS_M)
        waypoints.append(
            PatrolWaypoint(
                longitude=lon,
                latitude=lat,
                expected_speed=expected_speed,
            )
        )
    return waypoints


def _reorder_circle_waypoints_by_ownship(
    waypoints: List[PatrolWaypoint],
    center: GeoPoint,
    ownship_point: Optional[GeoPoint],
) -> List[PatrolWaypoint]:
    if ownship_point is None or not waypoints:
        return waypoints

    ownship_local = _project_point_to_local(ownship_point, ref_lon=center.longitude, ref_lat=center.latitude)
    ref_lat_rad = math.radians(center.latitude)
    cos_lat = max(math.cos(ref_lat_rad), 1e-12)

    best_idx = 0
    best_dist = None
    for idx, point in enumerate(waypoints):
        local = _LocalPoint(
            x=math.radians(point.longitude - center.longitude) * EARTH_RADIUS_M * cos_lat,
            y=math.radians(point.latitude - center.latitude) * EARTH_RADIUS_M,
        )
        dist = _distance_m(local.x - ownship_local.x, local.y - ownship_local.y)
        if best_dist is None or dist < best_dist:
            best_dist = dist
            best_idx = idx

    return waypoints[best_idx:] + waypoints[:best_idx]


def _prepend_start_waypoint(
    waypoints: List[PatrolWaypoint],
    start_point: GeoPoint,
    expected_speed: float,
) -> List[PatrolWaypoint]:
    start_waypoint = PatrolWaypoint(
        longitude=start_point.longitude,
        latitude=start_point.latitude,
        expected_speed=expected_speed,
    )
    if not waypoints:
        return [start_waypoint]
    first = waypoints[0]
    first_point = GeoPoint(longitude=first.longitude, latitude=first.latitude)
    if _haversine_distance_m(start_point, first_point) <= START_POINT_MIN_GAP_M:
        return waypoints
    return [start_waypoint, *waypoints]


def _build_circle_entry_point(center: GeoPoint, radius_m: float, ownship_point: GeoPoint) -> GeoPoint:
    ownship_local = _project_point_to_local(ownship_point, ref_lon=center.longitude, ref_lat=center.latitude)
    norm = _distance_m(ownship_local.x, ownship_local.y)
    if norm <= 1e-6:
        entry_local = _LocalPoint(x=radius_m, y=0.0)
    else:
        scale = radius_m / norm
        entry_local = _LocalPoint(x=ownship_local.x * scale, y=ownship_local.y * scale)
    return _project_from_local(entry_local, ref_lon=center.longitude, ref_lat=center.latitude)


def _build_polygon_entry_point(
    polygon_points_local: List[_LocalPoint],
    ref_lon: float,
    ref_lat: float,
    ownship_point: GeoPoint,
) -> GeoPoint:
    ownship_local = _project_point_to_local(ownship_point, ref_lon=ref_lon, ref_lat=ref_lat)
    nearest = min(
        polygon_points_local,
        key=lambda p: _distance_m(p.x - ownship_local.x, p.y - ownship_local.y),
    )
    return _project_from_local(nearest, ref_lon=ref_lon, ref_lat=ref_lat)


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


def _distance_point_to_segment(px: float, py: float, ax: float, ay: float, bx: float, by: float) -> float:
    vx = bx - ax
    vy = by - ay
    wx = px - ax
    wy = py - ay
    seg_len_sq = vx * vx + vy * vy
    if seg_len_sq <= 1e-12:
        return _distance_m(px - ax, py - ay)
    t = (wx * vx + wy * vy) / seg_len_sq
    t = min(max(t, 0.0), 1.0)
    cx = ax + t * vx
    cy = ay + t * vy
    return _distance_m(px - cx, py - cy)


def _min_distance_to_polygon_edges(point: _LocalPoint, polygon: List[Tuple[float, float]]) -> float:
    n = len(polygon)
    min_dist = float("inf")
    for i in range(n):
        ax, ay = polygon[i]
        bx, by = polygon[(i + 1) % n]
        dist = _distance_point_to_segment(point.x, point.y, ax, ay, bx, by)
        if dist < min_dist:
            min_dist = dist
    return min_dist


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


def _build_scan_positions(min_y: float, max_y: float, scan_margin: float, spacing: float) -> List[float]:
    span = max_y - min_y
    if span <= 2.0 * scan_margin + 1e-6:
        return [(min_y + max_y) / 2.0]

    start = min_y + scan_margin
    end = max_y - scan_margin
    if start > end:
        return [(min_y + max_y) / 2.0]

    ys = [start]
    while ys[-1] + spacing < end - 1e-6:
        ys.append(ys[-1] + spacing)
    if end - ys[-1] > 1e-6:
        ys.append(end)
    return ys


def _estimate_scan_count(min_y: float, max_y: float, scan_margin: float, spacing: float) -> int:
    return len(_build_scan_positions(min_y, max_y, scan_margin, spacing))


def _choose_sweep_angle(polygon: List[Tuple[float, float]], scan_margin: float, spacing: float) -> float:
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
        scan_count = _estimate_scan_count(min(ys), max(ys), scan_margin, spacing)
        path_proxy = scan_count * span_x + max(0, scan_count - 1) * spacing
        score = (scan_count, path_proxy, angle)
        if best_score is None or score < best_score:
            best_score = score
            best_angle = angle
    return best_angle


def _build_coverage_path(
    polygon: List[Tuple[float, float]],
    sweep_angle_deg: float,
    scan_margin: float,
    spacing: float,
    start_left_to_right: bool = True,
    reverse_scan_positions: bool = False,
) -> List[_LocalPoint]:
    rotated = [_rotate_xy(x, y, -sweep_angle_deg) for x, y in polygon]
    ys = [point[1] for point in rotated]
    scan_positions = _build_scan_positions(min(ys), max(ys), scan_margin, spacing)
    if reverse_scan_positions:
        scan_positions = list(reversed(scan_positions))

    # boundary_clearance is already reflected in scan_margin at the caller,
    # so we keep endpoint margin consistent with scanline margin.
    inner_margin = scan_margin

    raw_points: List[Tuple[float, float]] = []
    left_to_right = start_left_to_right
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
                inner_start = x_start + inner_margin
                inner_end = x_end - inner_margin
            else:
                inner_start = x_start - inner_margin
                inner_end = x_end + inner_margin

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


def _filter_points_in_safe_zone(
    points: List[_LocalPoint],
    polygon_xy: List[Tuple[float, float]],
    required_margin_m: float,
) -> List[_LocalPoint]:
    if required_margin_m <= 1e-6:
        return points
    safe_points: List[_LocalPoint] = []
    for point in points:
        if _min_distance_to_polygon_edges(point, polygon_xy) + 1e-6 >= required_margin_m:
            safe_points.append(point)
    return safe_points


def _compute_start_cost(
    points: List[_LocalPoint],
    ownship_point: _LocalPoint,
    ownship_heading_deg: Optional[float],
    turn_penalty_m_per_deg: float,
) -> float:
    if not points:
        return float("inf")

    first = points[0]
    distance_cost = _distance_m(first.x - ownship_point.x, first.y - ownship_point.y)
    if ownship_heading_deg is None or turn_penalty_m_per_deg <= 0:
        return distance_cost

    if len(points) >= 2:
        first_leg_dx = points[1].x - first.x
        first_leg_dy = points[1].y - first.y
        if _distance_m(first_leg_dx, first_leg_dy) > 1e-6:
            desired_heading = _bearing_from_vector(first_leg_dx, first_leg_dy)
        else:
            desired_heading = _bearing_from_vector(first.x - ownship_point.x, first.y - ownship_point.y)
    else:
        desired_heading = _bearing_from_vector(first.x - ownship_point.x, first.y - ownship_point.y)

    turn_cost = _min_turn_deg(ownship_heading_deg, desired_heading)
    return distance_cost + turn_penalty_m_per_deg * turn_cost


def _generate_candidate_paths(
    polygon_xy: List[Tuple[float, float]],
    sweep_angle_deg: float,
    scan_margin: float,
    spacing: float,
) -> List[List[_LocalPoint]]:
    candidates: List[List[_LocalPoint]] = []
    for reverse_scan_positions in (False, True):
        for start_left_to_right in (True, False):
            path = _build_coverage_path(
                polygon=polygon_xy,
                sweep_angle_deg=sweep_angle_deg,
                scan_margin=scan_margin,
                spacing=spacing,
                start_left_to_right=start_left_to_right,
                reverse_scan_positions=reverse_scan_positions,
            )
            if path:
                candidates.append(path)
    return candidates


def generate_simple_patrol_waypoints(
    task_area: TaskArea,
    expected_speed: float,
    num_passes: int = 4,
    ownship_point: Optional[GeoPoint] = None,
    ownship_heading_deg: Optional[float] = None,
    max_step_m: Optional[float] = None,
    scan_radius_m: Optional[float] = None,
    boundary_clearance_m: Optional[float] = None,
    start_turn_penalty_m_per_deg: float = 0.5,
) -> List[PatrolWaypoint]:
    turn_penalty = max(0.0, start_turn_penalty_m_per_deg)

    if task_area.area_type == "circle":
        if task_area.center is None or task_area.radius_m is None:
            return []
        waypoints = _build_circle_waypoints(
            center=task_area.center,
            radius_m=task_area.radius_m,
            expected_speed=expected_speed,
            num_points=max(12, num_passes * 3),
        )
        ordered = _reorder_circle_waypoints_by_ownship(waypoints, center=task_area.center, ownship_point=ownship_point)
        if ownship_point is None:
            return ordered
        entry_point = _build_circle_entry_point(task_area.center, task_area.radius_m, ownship_point)
        return _prepend_start_waypoint(ordered, entry_point, expected_speed)

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

    ys = [point.y for point in local_polygon]
    span_y = max(ys) - min(ys)
    if scan_radius_m is not None and scan_radius_m > 0:
        # When explicit scan radius is provided, enforce sensor-consistent lane spacing.
        search_radius = scan_radius_m
        spacing = max(2.0 * search_radius, 1.0)
    else:
        spacing = max(span_y / max(pass_count - 1, 1), 1.0)
        search_radius = spacing / 2.0
    boundary_clearance = (
        boundary_clearance_m
        if boundary_clearance_m is not None and boundary_clearance_m >= 0
        else min(max(spacing * 0.05, 0.0), 5.0)
    )

    required_safe_margin = max(search_radius - boundary_clearance, 0.0)
    scan_margin = required_safe_margin

    sweep_angle_deg = _choose_sweep_angle(
        polygon=polygon_xy,
        scan_margin=scan_margin,
        spacing=spacing,
    )
    candidate_paths = _generate_candidate_paths(
        polygon_xy=polygon_xy,
        sweep_angle_deg=sweep_angle_deg,
        scan_margin=scan_margin,
        spacing=spacing,
    )
    if not candidate_paths:
        candidate_paths = _generate_candidate_paths(
            polygon_xy=polygon_xy,
            sweep_angle_deg=sweep_angle_deg,
            scan_margin=search_radius,
            spacing=spacing,
        )

    if not candidate_paths:
        centroid = GeoPoint(longitude=ref_lon, latitude=ref_lat)
        return [
            PatrolWaypoint(
                longitude=centroid.longitude,
                latitude=centroid.latitude,
                expected_speed=expected_speed,
            )
        ]

    selected_path = candidate_paths[0]
    if ownship_point is not None:
        ownship_local = _project_point_to_local(ownship_point, ref_lon=ref_lon, ref_lat=ref_lat)
        selected_path = min(
            candidate_paths,
            key=lambda points: _compute_start_cost(
                points=points,
                ownship_point=ownship_local,
                ownship_heading_deg=ownship_heading_deg,
                turn_penalty_m_per_deg=turn_penalty,
            ),
        )

    dense_step = max_step_m if max_step_m is not None and max_step_m > 0 else max(spacing, 1.0)
    dense_waypoints = _densify_path(selected_path, max_step_m=dense_step)
    safe_waypoints = _filter_points_in_safe_zone(
        points=dense_waypoints,
        polygon_xy=polygon_xy,
        required_margin_m=required_safe_margin,
    )
    if safe_waypoints:
        dense_waypoints = safe_waypoints
    geo_waypoints = [
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
    if ownship_point is None:
        return geo_waypoints
    entry_point = _build_polygon_entry_point(local_polygon, ref_lon, ref_lat, ownship_point)
    return _prepend_start_waypoint(geo_waypoints, entry_point, expected_speed)
