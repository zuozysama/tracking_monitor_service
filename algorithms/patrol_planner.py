import math
from dataclasses import dataclass
from typing import List, Optional, Tuple

from domain.models import GeoPoint, PatrolWaypoint, TaskArea


EARTH_RADIUS_M = 6371000.0
START_POINT_MIN_GAP_M = 10.0
CIRCLE_COVERAGE_POLYGON_POINTS = 72


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


def _build_circle_boundary_points(center: GeoPoint, radius_m: float, count: int = CIRCLE_COVERAGE_POLYGON_POINTS) -> List[GeoPoint]:
    lat_rad = math.radians(center.latitude)
    cos_lat = max(math.cos(lat_rad), 1e-12)
    points: List[GeoPoint] = []
    for idx in range(max(12, count)):
        angle = 2.0 * math.pi * idx / max(12, count)
        dx = radius_m * math.cos(angle)
        dy = radius_m * math.sin(angle)
        points.append(
            GeoPoint(
                longitude=center.longitude + math.degrees(dx / (EARTH_RADIUS_M * cos_lat)),
                latitude=center.latitude + math.degrees(dy / EARTH_RADIUS_M),
            )
        )
    return points


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


def _polygon_signed_area(polygon: List[_LocalPoint]) -> float:
    area = 0.0
    for idx, point in enumerate(polygon):
        nxt = polygon[(idx + 1) % len(polygon)]
        area += point.x * nxt.y - nxt.x * point.y
    return area / 2.0


def _orientation(ax: float, ay: float, bx: float, by: float, cx: float, cy: float) -> float:
    return (bx - ax) * (cy - ay) - (by - ay) * (cx - ax)


def _segments_intersect(
    a: _LocalPoint,
    b: _LocalPoint,
    c: _LocalPoint,
    d: _LocalPoint,
    eps: float = 1e-6,
) -> bool:
    o1 = _orientation(a.x, a.y, b.x, b.y, c.x, c.y)
    o2 = _orientation(a.x, a.y, b.x, b.y, d.x, d.y)
    o3 = _orientation(c.x, c.y, d.x, d.y, a.x, a.y)
    o4 = _orientation(c.x, c.y, d.x, d.y, b.x, b.y)

    if o1 * o2 < -eps and o3 * o4 < -eps:
        return True
    if abs(o1) <= eps and _point_on_segment(c.x, c.y, a.x, a.y, b.x, b.y, eps=eps):
        return True
    if abs(o2) <= eps and _point_on_segment(d.x, d.y, a.x, a.y, b.x, b.y, eps=eps):
        return True
    if abs(o3) <= eps and _point_on_segment(a.x, a.y, c.x, c.y, d.x, d.y, eps=eps):
        return True
    if abs(o4) <= eps and _point_on_segment(b.x, b.y, c.x, c.y, d.x, d.y, eps=eps):
        return True
    return False


def _intersecting_edge_pair(polygon: List[_LocalPoint]) -> Optional[Tuple[int, int]]:
    n = len(polygon)
    for i in range(n):
        a1 = polygon[i]
        a2 = polygon[(i + 1) % n]
        for j in range(i + 1, n):
            if j == i or j == (i + 1) % n or i == (j + 1) % n:
                continue
            b1 = polygon[j]
            b2 = polygon[(j + 1) % n]
            if _segments_intersect(a1, a2, b1, b2):
                return i, j
    return None


def _polygon_has_self_intersection(polygon: List[_LocalPoint]) -> bool:
    return _intersecting_edge_pair(polygon) is not None


def _normalize_polygon_boundary(polygon: List[_LocalPoint]) -> List[_LocalPoint]:
    if len(polygon) < 3:
        return polygon

    normalized = list(polygon)
    if _distance_m(normalized[0].x - normalized[-1].x, normalized[0].y - normalized[-1].y) <= 1e-6:
        normalized = normalized[:-1]

    # If downlink points form a bow-tie shape, untangle crossings by reversing
    # the vertex chain between the two crossing edges. This preserves boundary
    # adjacency for already valid concave polygons instead of sorting by angle.
    for _ in range(len(normalized) * len(normalized)):
        pair = _intersecting_edge_pair(normalized)
        if pair is None:
            break
        i, j = pair
        if i > j:
            i, j = j, i
        normalized[i + 1 : j + 1] = reversed(normalized[i + 1 : j + 1])

    # Use a consistent clockwise winding for scanline operations and downstream
    # geometry. In local coordinates positive signed area means counterclockwise.
    if _polygon_signed_area(normalized) > 0:
        normalized = list(reversed(normalized))
    return normalized


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


def _min_distance_to_path(point: _LocalPoint, path: List[_LocalPoint]) -> float:
    if not path:
        return float("inf")
    min_dist = float("inf")
    for i in range(len(path) - 1):
        a = path[i]
        b = path[i + 1]
        dist = _distance_point_to_segment(point.x, point.y, a.x, a.y, b.x, b.y)
        if dist < min_dist:
            min_dist = dist
    return min_dist


def _convex_hull(points: List[_LocalPoint]) -> List[_LocalPoint]:
    # Monotone chain convex hull (returns points in CCW order)
    pts = sorted([(p.x, p.y) for p in points])
    if len(pts) <= 1:
        return [_LocalPoint(x=pts[0][0], y=pts[0][1])] if pts else []

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: List[Tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
            lower.pop()
        lower.append(p)

    upper: List[Tuple[float, float]] = []
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
            upper.pop()
        upper.append(p)

    hull = lower[:-1] + upper[:-1]
    return [_LocalPoint(x=x, y=y) for x, y in hull]


def _compute_uncovered_clusters(
    polygon_xy: List[Tuple[float, float]],
    path: List[_LocalPoint],
    spacing: float,
) -> List[List[_LocalPoint]]:
    if not polygon_xy or not path:
        return []

    # grid sampling step (half spacing for sensitivity)
    step = max(spacing * 0.5, 1.0)
    xs = [p[0] for p in polygon_xy]
    ys = [p[1] for p in polygon_xy]
    min_x, max_x = min(xs), max(xs)
    min_y, max_y = min(ys), max(ys)

    nx = int(math.ceil((max_x - min_x) / step)) + 1
    ny = int(math.ceil((max_y - min_y) / step)) + 1

    uncovered_cells = set()
    for i in range(nx):
        x = min_x + i * step
        for j in range(ny):
            y = min_y + j * step
            if not _point_in_polygon((x, y), polygon_xy):
                continue
            pt = _LocalPoint(x=x, y=y)
            dist = _min_distance_to_path(pt, path)
            if dist > spacing * 0.5 + 1e-6:
                uncovered_cells.add((i, j))

    # cluster adjacent cells (4-neighbor)
    clusters: List[List[_LocalPoint]] = []
    seen = set()
    for cell in list(uncovered_cells):
        if cell in seen:
            continue
        stack = [cell]
        comp = []
        while stack:
            ci, cj = stack.pop()
            if (ci, cj) in seen:
                continue
            seen.add((ci, cj))
            if (ci, cj) not in uncovered_cells:
                continue
            x = min_x + ci * step
            y = min_y + cj * step
            comp.append(_LocalPoint(x=x, y=y))
            for di, dj in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                ni, nj = ci + di, cj + dj
                if (ni, nj) in uncovered_cells and (ni, nj) not in seen:
                    stack.append((ni, nj))
        if comp:
            clusters.append(comp)

    return clusters


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

    usable_span = end - start
    if usable_span <= 1e-6:
        return [(start + end) / 2.0]

    lane_count = max(2, int(math.ceil(usable_span / max(spacing, 1.0))) + 1)
    actual_spacing = usable_span / max(lane_count - 1, 1)
    return [start + idx * actual_spacing for idx in range(lane_count)]


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
    endpoint_margin: float,
    spacing: float,
    start_left_to_right: bool = True,
    reverse_scan_positions: bool = False,
) -> List[_LocalPoint]:
    rotated = [_rotate_xy(x, y, -sweep_angle_deg) for x, y in polygon]
    ys = [point[1] for point in rotated]
    scan_positions = _build_scan_positions(min(ys), max(ys), scan_margin, spacing)
    if reverse_scan_positions:
        scan_positions = list(reversed(scan_positions))

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
                inner_start = x_start + endpoint_margin
                inner_end = x_end - endpoint_margin
            else:
                inner_start = x_start - endpoint_margin
                inner_end = x_end + endpoint_margin

            if abs(inner_end - inner_start) <= 1e-6:
                midpoint = (x_start + x_end) / 2.0
                raw_points.append(_rotate_xy(midpoint, y_scan, sweep_angle_deg))
                continue
            if x_end >= x_start and inner_end <= inner_start:
                midpoint = (x_start + x_end) / 2.0
                raw_points.append(_rotate_xy(midpoint, y_scan, sweep_angle_deg))
                continue
            if x_end < x_start and inner_end >= inner_start:
                midpoint = (x_start + x_end) / 2.0
                raw_points.append(_rotate_xy(midpoint, y_scan, sweep_angle_deg))
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


def _compute_entry_start_cost(
    points: List[_LocalPoint],
    entry_point: _LocalPoint,
    approach_heading_deg: Optional[float],
    turn_penalty_m_per_deg: float,
) -> float:
    if not points:
        return float("inf")

    first = points[0]
    distance_cost = _distance_m(first.x - entry_point.x, first.y - entry_point.y)
    if approach_heading_deg is None or turn_penalty_m_per_deg <= 0:
        return distance_cost

    desired_heading = _bearing_from_vector(first.x - entry_point.x, first.y - entry_point.y)
    turn_cost = _min_turn_deg(approach_heading_deg, desired_heading)
    return distance_cost + turn_penalty_m_per_deg * turn_cost


def _compute_entry_scan_offset(
    points: List[_LocalPoint],
    entry_point: _LocalPoint,
    sweep_angle_deg: float,
) -> float:
    if not points:
        return float("inf")

    _, entry_scan_y = _rotate_xy(entry_point.x, entry_point.y, -sweep_angle_deg)
    _, first_scan_y = _rotate_xy(points[0].x, points[0].y, -sweep_angle_deg)
    return abs(first_scan_y - entry_scan_y)


def _build_inside_start_variants(points: List[_LocalPoint]) -> List[List[_LocalPoint]]:
    if not points:
        return []

    # Coverage paths are open polylines. Cutting them from the middle can
    # create non-adjacent jumps, so inside starts only choose either end.
    forward = list(points)
    backward = list(reversed(points))
    if len(points) == 1:
        return [forward]
    return [forward, backward]


def _generate_candidate_paths(
    polygon_xy: List[Tuple[float, float]],
    sweep_angle_deg: float,
    scan_margin: float,
    endpoint_margin: float,
    spacing: float,
) -> List[List[_LocalPoint]]:
    candidates: List[List[_LocalPoint]] = []
    for reverse_scan_positions in (False, True):
        for start_left_to_right in (True, False):
            path = _build_coverage_path(
                polygon=polygon_xy,
                sweep_angle_deg=sweep_angle_deg,
                scan_margin=scan_margin,
                endpoint_margin=endpoint_margin,
                spacing=spacing,
                start_left_to_right=start_left_to_right,
                reverse_scan_positions=reverse_scan_positions,
            )
            if path:
                candidates.append(path)
    return candidates


def _line_intersection(a1: _LocalPoint, a2: _LocalPoint, b1: _LocalPoint, b2: _LocalPoint) -> Optional[_LocalPoint]:
    x1, y1 = a1.x, a1.y
    x2, y2 = a2.x, a2.y
    x3, y3 = b1.x, b1.y
    x4, y4 = b2.x, b2.y
    denom = (x1 - x2) * (y3 - y4) - (y1 - y2) * (x3 - x4)
    if abs(denom) <= 1e-12:
        return None
    px = ((x1 * y2 - y1 * x2) * (x3 - x4) - (x1 - x2) * (x3 * y4 - y3 * x4)) / denom
    py = ((x1 * y2 - y1 * x2) * (y3 - y4) - (y1 - y2) * (x3 * y4 - y3 * x4)) / denom
    return _LocalPoint(x=px, y=py)


def _offset_polygon_inward(
    polygon: List[_LocalPoint],
    offset: float,
    max_vertex_offset: Optional[float] = None,
) -> List[_LocalPoint]:
    """Offset a clockwise polygon inward.

    Parameters
    ----------
    polygon
        Source polygon vertices in clockwise order.
    offset
        Edge offset distance (positive = inward).
    max_vertex_offset
        If set, clamp each offset vertex so its distance from the
        corresponding original vertex does not exceed this value.
        This implements a chamfer (cut-corner) offset — sharp vertices
        are pulled back along the angle bisector to prevent excessive
        miter depth.  The edge offset *offset* is unaffected.
    """
    n = len(polygon)
    if n < 3 or offset <= 0:
        return list(polygon)

    offset_lines: List[Tuple[_LocalPoint, _LocalPoint]] = []
    for i in range(n):
        a = polygon[i]
        b = polygon[(i + 1) % n]
        dx = b.x - a.x
        dy = b.y - a.y
        seg_len = math.hypot(dx, dy)
        if seg_len <= 1e-12:
            nx, ny = 0.0, 0.0
        else:
            # inward normal for clockwise polygon is (dy, -dx) normalized
            nx = dy / seg_len
            ny = -dx / seg_len
        a_off = _LocalPoint(x=a.x + nx * offset, y=a.y + ny * offset)
        b_off = _LocalPoint(x=b.x + nx * offset, y=b.y + ny * offset)
        offset_lines.append((a_off, b_off))

    new_pts: List[_LocalPoint] = []
    for i in range(n):
        prev_line = offset_lines[(i - 1) % n]
        cur_line = offset_lines[i]
        intersect = _line_intersection(prev_line[0], prev_line[1], cur_line[0], cur_line[1])
        if intersect is None:
            # fallback to midpoint between the two offset segment endpoints
            mid_x = (prev_line[1].x + cur_line[0].x) / 2.0
            mid_y = (prev_line[1].y + cur_line[0].y) / 2.0
            new_pts.append(_LocalPoint(x=mid_x, y=mid_y))
        else:
            new_pts.append(intersect)

    # Chamfer: clamp vertex offset so sharp corners don't recede too far.
    if max_vertex_offset is not None and max_vertex_offset > 1e-6:
        for i in range(n):
            dx = new_pts[i].x - polygon[i].x
            dy = new_pts[i].y - polygon[i].y
            dist = math.hypot(dx, dy)
            if dist > max_vertex_offset:
                scale = max_vertex_offset / dist
                new_pts[i] = _LocalPoint(
                    x=polygon[i].x + dx * scale,
                    y=polygon[i].y + dy * scale,
                )

    # Clean and normalize
    cleaned = _dedupe_path_points([(p.x, p.y) for p in new_pts])
    result = [_LocalPoint(x=x, y=y) for x, y in cleaned]
    result = _normalize_polygon_boundary(result)
    return result


def _build_concentric_loops(
    local_polygon: List[_LocalPoint],
    spacing: float,
    max_loops: int,
    start_offset: float = 0.0,
    max_vertex_offset: Optional[float] = None,
) -> List[List[_LocalPoint]]:
    def _build_concentric_loops_inner(
        local_polygon: List[_LocalPoint],
        spacing: float,
        max_loops: int,
        start_offset: float = 0.0,
        max_vertex_offset: Optional[float] = None,
    ) -> List[List[_LocalPoint]]:
        loops: List[List[_LocalPoint]] = []
        if not local_polygon or spacing <= 1e-6 or max_loops <= 0:
            return loops

        # Start from an outward-facing loop: either the original boundary
        # (hug the edge) or an initial inward offset when explicitly requested.
        # Chamfer (max_vertex_offset) is only applied to this first offset —
        # subsequent spacing offsets use regular miter to avoid topology blowup.
        if start_offset and start_offset > 1e-6:
            current = _offset_polygon_inward(local_polygon, start_offset, max_vertex_offset=max_vertex_offset)
        else:
            current = list(local_polygon)

        # Include the current outermost loop (original boundary or inset)
        if len(current) >= 3:
            loops.append(current)

        for _ in range(max_loops):
            # compute inward offset polygon (regular miter, no chamfer)
            next_poly = _offset_polygon_inward(current, spacing)
            if len(next_poly) < 3:
                break
            # ensure it lies strictly inside previous polygon
            xs = [p.x for p in next_poly]
            ys = [p.y for p in next_poly]
            centroid = ((sum(xs) / len(xs)), (sum(ys) / len(ys)))
            if not _point_in_polygon(centroid, [(p.x, p.y) for p in current]):
                break
            # reject self-intersecting polygons — offset may cause edges
            # to cross when the polygon is too narrow for the spacing.
            if _polygon_has_self_intersection(next_poly):
                break
            # reject degenerate polygons with very short edges (offset
            # distortion created nearly-coincident vertices).
            min_edge = min(
                _distance_m(next_poly[i].x - next_poly[(i + 1) % len(next_poly)].x,
                            next_poly[i].y - next_poly[(i + 1) % len(next_poly)].y)
                for i in range(len(next_poly))
            )
            if min_edge < spacing * 0.15:
                break
            # check area shrink
            area_prev = abs(_polygon_signed_area(current))
            area_next = abs(_polygon_signed_area(next_poly))
            if area_next <= 1e-6 or area_next >= area_prev - 1e-6:
                break
            loops.append(next_poly)
            current = next_poly

        return loops

    # Expose a stable API with optional start_offset via keyword on call.
    # Default behaviour (no start_offset) will be handled by caller.
    return _build_concentric_loops_inner(local_polygon, spacing, max_loops, start_offset, max_vertex_offset)


def _rotate_path_to_nearest(path: List[_LocalPoint], ref: _LocalPoint) -> List[_LocalPoint]:
    """Rotate a path so the vertex nearest to `ref` becomes the first point."""
    if not path:
        return path
    best_i = min(range(len(path)), key=lambda k: _distance_m(path[k].x - ref.x, path[k].y - ref.y))
    return path[best_i:] + path[:best_i]


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
    pattern: str = "lawnmower",
) -> List[PatrolWaypoint]:
    turn_penalty = max(0.0, start_turn_penalty_m_per_deg)

    original_area_was_circle = False
    if task_area.area_type == "circle":
        if task_area.center is None or task_area.radius_m is None:
            return []
        circle_area = TaskArea(
            area_type="polygon",
            points=_build_circle_boundary_points(task_area.center, task_area.radius_m),
        )
        # convert to polygon but do not return immediately; remember original
        original_area_was_circle = True
        task_area = circle_area

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
    local_polygon = _normalize_polygon_boundary(local_polygon)
    polygon_xy = [(point.x, point.y) for point in local_polygon]

    ys = [point.y for point in local_polygon]
    span_y = max(ys) - min(ys)
    if scan_radius_m is not None and scan_radius_m > 0:
        # Use the sensor diameter as the maximum lane spacing. Scan positions
        # are then evenly distributed for the resulting minimum lane count.
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

    scan_margin = max(search_radius * 0.5, boundary_clearance)
    endpoint_margin = max(search_radius * 0.5, boundary_clearance)

    sweep_angle_deg = _choose_sweep_angle(
        polygon=polygon_xy,
        scan_margin=scan_margin,
        spacing=spacing,
    )
    # Compute ownship local point early to decide circle special-casing
    ownship_local = None
    if ownship_point is not None:
        ownship_local = _project_point_to_local(ownship_point, ref_lon=ref_lon, ref_lat=ref_lat)

    # Prefer concentric inward-offset loops (回字形) starting from an inset
    # defined by endpoint_margin. If that fails, fall back to lawnmower.
    candidate_paths: List[List[_LocalPoint]] = []
    used_loops = False
    raw_loops: Optional[List[List[_LocalPoint]]] = None
    # Build concentric loops.  Use the full sensor radius as the edge offset
    # (zero waste at straight edges) but clamp the vertex miter depth to the
    # same value (chamfer offset).  Sharp corners are pulled back along the
    # angle bisector so they stay within scan coverage.
    # Per Maths.md §5.2: the outermost loop is inset by the full sensor
    # radius R (= search_radius) so the sensor coverage outer edge
    # reaches the polygon boundary (zero waste on straight edges).
    # Chamfer (max_vertex_offset=R) limits miter blowup at sharp corners.
    loops = _build_concentric_loops(
        local_polygon,
        spacing,
        pass_count,
        start_offset=search_radius,
        max_vertex_offset=search_radius,
    )
    ownship_inside_circle = original_area_was_circle and ownship_local is not None and _point_in_polygon((ownship_local.x, ownship_local.y), polygon_xy)

    if pattern == "lawnmower":
        # Force scanline generation
        candidate_paths = _generate_candidate_paths(
            polygon_xy=polygon_xy,
            sweep_angle_deg=sweep_angle_deg,
            scan_margin=scan_margin,
            endpoint_margin=endpoint_margin,
            spacing=spacing,
        )
        if not candidate_paths:
            candidate_paths = _generate_candidate_paths(
                polygon_xy=polygon_xy,
                sweep_angle_deg=sweep_angle_deg,
                scan_margin=search_radius,
                endpoint_margin=endpoint_margin,
                spacing=spacing,
            )
    elif pattern == "concentric":
        # Use concentric loops. Defer rotation/densification until we know
        # the ownship/entry reference so we can implement a per-loop
        # "complete-one-loop-then-shrink" behavior (not a stitched spiral).
        if loops:
            raw_loops = loops
            used_loops = True
        else:
            # fall back to scanline if no loops
            candidate_paths = _generate_candidate_paths(
                polygon_xy=polygon_xy,
                sweep_angle_deg=sweep_angle_deg,
                scan_margin=scan_margin,
                endpoint_margin=endpoint_margin,
                spacing=spacing,
            )
            if not candidate_paths:
                candidate_paths = _generate_candidate_paths(
                    polygon_xy=polygon_xy,
                    sweep_angle_deg=sweep_angle_deg,
                    scan_margin=search_radius,
                    endpoint_margin=endpoint_margin,
                    spacing=spacing,
                )
    else:
        # Default to lawnmower (scanline) generation for any unrecognised pattern.
        candidate_paths = _generate_candidate_paths(
            polygon_xy=polygon_xy,
            sweep_angle_deg=sweep_angle_deg,
            scan_margin=scan_margin,
            endpoint_margin=endpoint_margin,
            spacing=spacing,
        )
        if not candidate_paths:
            candidate_paths = _generate_candidate_paths(
                polygon_xy=polygon_xy,
                sweep_angle_deg=sweep_angle_deg,
                scan_margin=search_radius,
                endpoint_margin=endpoint_margin,
                spacing=spacing,
            )

    if not candidate_paths and not raw_loops:
        centroid = GeoPoint(longitude=ref_lon, latitude=ref_lat)
        return [
            PatrolWaypoint(
                longitude=centroid.longitude,
                latitude=centroid.latitude,
                expected_speed=expected_speed,
            )
        ]

    dense_step = max_step_m if max_step_m is not None and max_step_m > 0 else max(spacing, 1.0)
    prepared_candidate_paths: List[List[_LocalPoint]] = []

    # If we reserved raw_loops to implement per-loop behavior, build
    # prepared paths now after we know ownship/entry so we can rotate
    # each loop to the chosen anchor and close the loop (complete one
    # circuit before moving inward).
    if 'used_loops' in locals() and used_loops and raw_loops:
        # If no ownship provided, choose a sensible default anchor (polygon
        # centroid) and build per-loop closed paths now. If ownship is
        # provided we defer to the ownship-specific handling below so the
        # start/entry logic can be applied.
        if ownship_local is None:
            xs = [p.x for p in local_polygon]
            ys = [p.y for p in local_polygon]
            centroid_local = _LocalPoint(x=sum(xs) / len(xs), y=sum(ys) / len(ys))
            for loop in raw_loops:
                if not loop:
                    continue
                # densify the raw loop first, then rotate the densified path
                # so we start at the point nearest to the anchor (centroid).
                loop_closed = list(loop) + ([loop[0]] if len(loop) >= 1 and _distance_m(loop[0].x - loop[-1].x, loop[0].y - loop[-1].y) > 1e-6 else [])
                dense_raw = _densify_path(loop_closed or list(loop), max_step_m=dense_step)
                if not dense_raw:
                    continue
                dense_rotated = _rotate_path_to_nearest(dense_raw, centroid_local)
                if len(dense_rotated) >= 1 and _distance_m(dense_rotated[0].x - dense_rotated[-1].x, dense_rotated[0].y - dense_rotated[-1].y) > 1e-6:
                    deduped = _dedupe_path_points(
                        [(p.x, p.y) for p in list(dense_rotated) + [dense_rotated[0]]]
                    )
                    dense_rotated_closed = [_LocalPoint(x=x, y=y) for x, y in deduped]
                else:
                    dense_rotated_closed = list(dense_rotated)
                safe_path = _filter_points_in_safe_zone(
                    points=dense_rotated_closed,
                    polygon_xy=polygon_xy,
                    required_margin_m=boundary_clearance,
                )
                prepared_candidate_paths.append(safe_path if safe_path else dense_rotated_closed)
    else:
        for path in candidate_paths:
            dense_path = _densify_path(path, max_step_m=dense_step)
            safe_path = _filter_points_in_safe_zone(
                points=dense_path,
                polygon_xy=polygon_xy,
                required_margin_m=boundary_clearance,
            )
            prepared_candidate_paths.append(safe_path if safe_path else dense_path)

    entry_point = None
    entry_local = None
    approach_heading_deg = None
    start_point = None
    if prepared_candidate_paths:
        if 'used_loops' in locals() and used_loops:
            # Flatten outer->inner loops into a single path, skipping the
            # closing point of each loop (the first vertex, which appears
            # again at the end). The loop ends at its last distinct vertex
            # before transitioning to the next inner loop.
            selected_path: List[_LocalPoint] = []
            for p in prepared_candidate_paths:
                selected_path.extend(p[:-1])  # skip closing point
        else:
            selected_path = prepared_candidate_paths[0]
    else:
        selected_path = []

    if ownship_point is not None:
        ownship_local = _project_point_to_local(ownship_point, ref_lon=ref_lon, ref_lat=ref_lat)
        # If we reserved raw_loops for per-loop behavior, build the actual
        # prepared_candidate_paths now using anchor based on ownship (inside
        # => nearest path point; outside => polygon vertex then nearest).
        if 'used_loops' in locals() and used_loops and raw_loops:
            prepared_candidate_paths = []
            # Determine anchor based on whether ownship is inside or outside.
            # Outside: anchor is the nearest polygon vertex (entry).
            # Inside: anchor is the ownship itself.
            if _point_in_polygon((ownship_local.x, ownship_local.y), polygon_xy):
                anchor_local = ownship_local
                start_point = None
            else:
                entry_point = _build_polygon_entry_point(local_polygon, ref_lon, ref_lat, ownship_point)
                start_point = entry_point
                entry_local = _project_point_to_local(entry_point, ref_lon=ref_lon, ref_lat=ref_lat)
                anchor_local = entry_local
                if _distance_m(entry_local.x - ownship_local.x, entry_local.y - ownship_local.y) > 1e-6:
                    approach_heading_deg = _bearing_from_vector(entry_local.x - ownship_local.x, entry_local.y - ownship_local.y)
                else:
                    approach_heading_deg = ownship_heading_deg

            # For each concentric loop, rotate so the vertex nearest to the
            # anchor becomes the start, close the loop (return to start),
            # then densify and filter.
            for loop in raw_loops:
                if not loop:
                    continue
                # densify loop first, then rotate densified points to start at
                # the point nearest to the anchor_local so vessel goes to the
                # closest path point when starting inside/outside.
                loop_closed = list(loop) + ([loop[0]] if len(loop) >= 1 and _distance_m(loop[0].x - loop[-1].x, loop[0].y - loop[-1].y) > 1e-6 else [])
                dense_raw = _densify_path(loop_closed or list(loop), max_step_m=dense_step)
                if not dense_raw:
                    continue
                dense_rotated = _rotate_path_to_nearest(dense_raw, anchor_local)
                if len(dense_rotated) >= 1 and _distance_m(dense_rotated[0].x - dense_rotated[-1].x, dense_rotated[0].y - dense_rotated[-1].y) > 1e-6:
                    deduped = _dedupe_path_points(
                        [(p.x, p.y) for p in list(dense_rotated) + [dense_rotated[0]]]
                    )
                    dense_rotated_closed = [_LocalPoint(x=x, y=y) for x, y in deduped]
                else:
                    dense_rotated_closed = list(dense_rotated)

                safe_path = _filter_points_in_safe_zone(
                    points=dense_rotated_closed,
                    polygon_xy=polygon_xy,
                    required_margin_m=boundary_clearance,
                )
                prepared_candidate_paths.append(safe_path if safe_path else dense_rotated_closed)

            # Flatten outer->inner loops into selected_path, skipping the
            # closing point of each loop (the first vertex, which appears
            # again at the end). The loop ends at its last distinct vertex
            # before transitioning to the next inner loop.
            selected_path = []
            for p in prepared_candidate_paths:
                selected_path.extend(p[:-1])  # skip closing point
            # Each loop was already rotated to start nearest to the anchor
            # (ownship when inside, entry vertex when outside). The flattened
            # path already has the correct ordering — no second rotation needed.
        else:
            # fallback to previous behaviour for non-stitched candidate paths
            if _point_in_polygon((ownship_local.x, ownship_local.y), polygon_xy):
                start_point = ownship_point
                inside_start_variants: List[List[_LocalPoint]] = []
                for path in prepared_candidate_paths:
                    inside_start_variants.extend(_build_inside_start_variants(path))
                if inside_start_variants:
                    prepared_candidate_paths = inside_start_variants
                selected_path = min(
                    prepared_candidate_paths,
                    key=lambda points: _compute_start_cost(
                        points=points,
                        ownship_point=ownship_local,
                        ownship_heading_deg=ownship_heading_deg,
                        turn_penalty_m_per_deg=turn_penalty,
                    ),
                )
            else:
                entry_point = _build_polygon_entry_point(local_polygon, ref_lon, ref_lat, ownship_point)
                start_point = entry_point
                entry_local = _project_point_to_local(entry_point, ref_lon=ref_lon, ref_lat=ref_lat)
                if _distance_m(entry_local.x - ownship_local.x, entry_local.y - ownship_local.y) > 1e-6:
                    approach_heading_deg = _bearing_from_vector(entry_local.x - ownship_local.x, entry_local.y - ownship_local.y)
                else:
                    approach_heading_deg = ownship_heading_deg
                # Extend candidates with forward/backward variants so the path
                # can start from either end, minimising the jump from the entry
                # vertex to the first coverage waypoint.
                outside_start_variants: List[List[_LocalPoint]] = []
                for path in prepared_candidate_paths:
                    outside_start_variants.extend(_build_inside_start_variants(path))
                if outside_start_variants:
                    prepared_candidate_paths = outside_start_variants
                selected_path = min(
                    prepared_candidate_paths,
                    key=lambda points: (
                        _compute_entry_scan_offset(
                            points=points,
                            entry_point=entry_local,
                            sweep_angle_deg=sweep_angle_deg,
                        ),
                        _compute_entry_start_cost(
                            points=points,
                            entry_point=entry_local,
                            approach_heading_deg=approach_heading_deg,
                            turn_penalty_m_per_deg=turn_penalty,
                        ),
                        _compute_start_cost(
                            points=points,
                            ownship_point=ownship_local,
                            ownship_heading_deg=ownship_heading_deg,
                            turn_penalty_m_per_deg=turn_penalty,
                        ),
                    ),
                )

    # If concentric loops were used as the main pattern, detect uncovered
    # pockets (cells that lie farther than spacing/2 from any path) and
    # fill them with local lawnmower patches.
    if 'used_loops' in locals() and used_loops and selected_path:
        clusters = _compute_uncovered_clusters(polygon_xy, selected_path, spacing)
        for comp in clusters:
            if len(comp) < 4:
                continue
            hull = _convex_hull(comp)
            if len(hull) < 3:
                continue
            cluster_xy = [(p.x, p.y) for p in hull]
            # choose a sweep angle appropriate for the cluster and generate candidates
            local_sweep = _choose_sweep_angle(cluster_xy, scan_margin, spacing)
            local_candidates = _generate_candidate_paths(
                polygon_xy=cluster_xy,
                sweep_angle_deg=local_sweep,
                scan_margin=scan_margin,
                endpoint_margin=endpoint_margin,
                spacing=spacing,
            )
            if not local_candidates:
                continue
            fill_path = local_candidates[0]
            dense_fill = _densify_path(fill_path, max_step_m=dense_step)
            safe_fill = _filter_points_in_safe_zone(points=dense_fill, polygon_xy=polygon_xy, required_margin_m=boundary_clearance)
            insert_fill = safe_fill if safe_fill else dense_fill
            if not insert_fill:
                continue
            # Append the fill patch at the end of the path rather than
            # inserting mid-path, which would create two transition jumps
            # (main→fill and fill→main).  The vessel traverses all
            # concentric loops first, then covers any uncovered pockets.
            selected_path.extend(insert_fill)

        # Remove duplicate consecutive points that may arise from fill
        # patches whose path shares vertices with the main concentric route.
        deduped = _dedupe_path_points([(p.x, p.y) for p in selected_path])
        selected_path = [_LocalPoint(x=x, y=y) for x, y in deduped]

    geo_waypoints = [
        PatrolWaypoint(
            longitude=geo_point.longitude,
            latitude=geo_point.latitude,
            expected_speed=expected_speed,
        )
        for geo_point in (
            _project_from_local(point, ref_lon=ref_lon, ref_lat=ref_lat)
            for point in selected_path
        )
    ]
    if ownship_point is None:
        return geo_waypoints
    # start_point is None when ownship is inside — the path already starts at
    # the nearest point to ownship, no need to prepend a separate waypoint.
    if start_point is None:
        return geo_waypoints

    # When the vessel is outside, prepend the entry polygon vertex as the
    # first waypoint (hard requirement: go to polygon vertex first, then
    # to the nearest path point on the concentric route).
    if ownship_local is not None and not _point_in_polygon((ownship_local.x, ownship_local.y), polygon_xy):
        start_waypoint = PatrolWaypoint(
            longitude=start_point.longitude,
            latitude=start_point.latitude,
            expected_speed=expected_speed,
        )
        return [start_waypoint, *geo_waypoints]

    return _prepend_start_waypoint(geo_waypoints, start_point, expected_speed)
