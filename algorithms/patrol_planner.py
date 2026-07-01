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


def _simplify_collinear_path(points: List[_LocalPoint], eps: float = 1.0) -> List[_LocalPoint]:
    """Remove collinear intermediate points, keeping only corners and anchors.

    For each triplet A→B→C, if B lies within *eps* metres of the straight
    line segment A‑C then B is redundant and is removed.  This turns
    densely‑interpolated polygon edges into single straight segments.
    """
    if len(points) <= 2:
        return list(points)

    simplified: List[_LocalPoint] = [points[0]]
    for i in range(1, len(points) - 1):
        a = points[i - 1]
        b = points[i]
        c = points[i + 1]
        dist = _distance_point_to_segment(b.x, b.y, a.x, a.y, c.x, c.y)
        if dist > eps:
            simplified.append(b)
    simplified.append(points[-1])
    return simplified


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


def _polygon_is_concave(polygon: List[_LocalPoint]) -> bool:
    """Check whether a polygon has at least one concave (reflex) vertex.

    A vertex is concave when the cross product of its incident edges has
    the opposite sign from the polygon's signed area (i.e. the interior
    angle > 180°).  Clockwise polygon → positive cross = concave.
    """
    n = len(polygon)
    if n < 4:
        return False
    sign = 1.0 if _polygon_signed_area(polygon) > 0 else -1.0
    for i in range(n):
        a = polygon[(i - 1) % n]
        b = polygon[i]
        c = polygon[(i + 1) % n]
        cross = (b.x - a.x) * (c.y - b.y) - (b.y - a.y) * (c.x - b.x)
        if cross * sign < -1e-9:
            return True
    return False


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


def _compute_endpoint_distance(
    points: List[_LocalPoint],
    target_point: _LocalPoint,
) -> float:
    """计算路径终点到目标点（断点）的距离"""
    if not points:
        return float("inf")
    last = points[-1]
    return _distance_m(last.x - target_point.x, last.y - target_point.y)


def _build_inside_start_variants(points: List[_LocalPoint]) -> List[List[_LocalPoint]]:
    """生成 lawnmower 开放折线的起点变体。

    对于开放折线（lawnmower 扫线路径），只保留 forward（原始顺序）
    和 backward（完全反转）两种变体。不从中间切开——切开会导致
    不连续跳跃（非相邻航点间的大跨度移动）和覆盖遗漏。

    Concentric 回字形路径有自己的起点旋转逻辑（_rotate_path_to_nearest），
    不走这里。
    """
    if not points:
        return []

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


def _compute_anchor_transition(
    prev_raw: List[_LocalPoint],
    curr_raw: List[_LocalPoint],
    prev_dense_closed: List[_LocalPoint],
    anchor_local: _LocalPoint,
) -> Tuple[Optional[_LocalPoint], int]:
    """Compute anchor transition point between two concentric loops.

    The anchor is the intersection of the extended direction lines of:
    - The **last edge** of the previous loop (from V_{s-1} back to V_s) —
      this is the edge we cut short.
    - The **edge after the start vertex** (V_s → V_{s+1}) of the *next*
      loop — guaranteed to be a different edge, so the lines always
      intersect at a finite point near the shared vertex V_s.

    *anchor_local* is the reference point that was used to rotate the
    previous loop; its nearest raw vertex gives us the start index *s*.

    The previous loop is truncated at V_{s-1} and routed *via* the anchor
    (a transit point before continuing to the next loop's start).  The
    current loop is **not** modified.

    Returns
    -------
    (anchor_point, cut_idx)
        anchor_point — the transit point to route through.
        cut_idx — index in *prev_dense_closed* at which to truncate (the
                  position of V_{s-1}, the last raw vertex before close).
        (None, -1) if the anchor cannot be computed.
    """
    n = len(prev_raw)
    if n < 3 or len(curr_raw) < 3 or len(prev_dense_closed) < 3:
        return None, -1

    # Determine start vertex index from the anchor that was used for rotation.
    # Using anchor_local directly is more reliable than prev_dense_closed[0],
    # which may lie on an edge midpoint (ambiguous nearest vertex).
    start_idx = min(
        range(n),
        key=lambda k: _distance_m(prev_raw[k].x - anchor_local.x, prev_raw[k].y - anchor_local.y),
    )

    # --- Last edge of previous loop: from V_{s-1} back to V_s ---
    last_a = prev_raw[(start_idx - 1) % n]   # V_{s-1} — last raw vertex
    last_b = prev_raw[start_idx % n]          # V_s      — start vertex

    # --- Edge after the start vertex: (V_s → V_{s+1}) of the next loop ---
    # Guaranteed to be DIFFERENT from the last edge, so lines always intersect.
    next_a = curr_raw[start_idx % n]
    next_b = curr_raw[(start_idx + 1) % n]

    anchor = _line_intersection(last_a, last_b, next_a, next_b)
    if anchor is None:
        return None, -1

    # --- Cut point: truncate at V_{s-1} ---
    target = prev_raw[(start_idx - 1) % n]
    cut_idx = min(
        range(len(prev_dense_closed)),
        key=lambda k: _distance_m(prev_dense_closed[k].x - target.x, prev_dense_closed[k].y - target.y),
    )

    return anchor, cut_idx


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
    """Build concentric loops via centroid interpolation.

    Unlike geometric polygon offset (which breaks down on irregular
    shapes), this approach interpolates each vertex toward the polygon
    centroid by a ratio proportional to the requested edge offset.
    The result is a set of geometrically similar shrinking polygons
    that work correctly for any convex or mildly concave shape.
    """
    loops: List[List[_LocalPoint]] = []
    if not local_polygon or len(local_polygon) < 3 or spacing <= 1e-6 or max_loops <= 0:
        return loops

    # Calculate centroid (average of vertices)
    xs = [p.x for p in local_polygon]
    ys = [p.y for p in local_polygon]
    cx = sum(xs) / len(xs)
    cy = sum(ys) / len(ys)
    centroid = _LocalPoint(x=cx, y=cy)

    # Characteristic radius: average distance from centroid to each vertex.
    # This gives a stable reference for converting offset distances to
    # interpolation ratios, adaptive to any polygon size.
    avg_radius = sum(_distance_m(p.x - cx, p.y - cy) for p in local_polygon) / len(local_polygon)
    if avg_radius <= 1e-6:
        return loops

    # Determine the number of loops including the optional start_offset.
    # start_offset is the inset for the first loop; each subsequent loop
    # moves further inward by spacing.
    total_loops = min(max_loops + 1, 50)  # safety cap

    # Use a fine step for inner loops so the last loop lands within
    # sensor radius of the centroid, ensuring complete coverage.
    fine_step = max(spacing * 0.5, 1.0)

    i = 0
    offset_dist = start_offset
    while i < total_loops:
        ratio = min(offset_dist / avg_radius, 1.0 - 1e-9)
        if ratio <= 0.0:
            i += 1
            offset_dist = start_offset + i * spacing
            continue

        loop = [
            _LocalPoint(
                x=cx + (p.x - cx) * (1.0 - ratio),
                y=cy + (p.y - cy) * (1.0 - ratio),
            )
            for p in local_polygon
        ]
        loops.append(loop)

        # Stop when this loop alone already covers the centroid
        # (sensor radius ≈ spacing / 2, so loop_radius ≤ spacing / 2
        #  means the sensor extends past the centre).
        loop_radius = avg_radius * (1.0 - ratio)
        if loop_radius <= spacing * 0.5:
            break

        i += 1
        next_offset = start_offset + i * spacing
        # If the remaining gap to centroid is less than one full spacing,
        # switch to fine step so we don't jump past the centre.
        remaining = avg_radius - offset_dist
        if remaining < spacing:
            offset_dist = offset_dist + fine_step
        else:
            offset_dist = next_offset

    return loops


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
    endpoint_weight: float = 1.0,
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
        # Helper: generate paths with a given spacing
        def _gen_paths(s: float) -> List[List[_LocalPoint]]:
            sm = max(s * 0.5, boundary_clearance)
            paths = _generate_candidate_paths(
                polygon_xy=polygon_xy,
                sweep_angle_deg=sweep_angle_deg,
                scan_margin=sm,
                endpoint_margin=endpoint_margin,
                spacing=s,
            )
            if not paths:
                paths = _generate_candidate_paths(
                    polygon_xy=polygon_xy,
                    sweep_angle_deg=sweep_angle_deg,
                    scan_margin=s,
                    endpoint_margin=endpoint_margin,
                    spacing=s,
                )
            return paths

        # Collect all path variants with different scan-line counts
        all_paths: List[List[_LocalPoint]] = []
        # Base: use original spacing (from scan_radius or pass_count)
        all_paths.extend(_gen_paths(spacing))
        # Explore nearby pass counts to get better endpoint alignment
        if ownship_point is not None:
            for delta in (-2, -1, 0, 1, 2):
                adj = max(2, pass_count + delta)
                s = max(span_y / max(adj - 1, 1), 1.0)
                adj_paths = _gen_paths(s)
                all_paths.extend(adj_paths)
                for p in adj_paths:
                    rp = list(reversed(p))
                    if rp:
                        all_paths.append(rp)
        candidate_paths = all_paths
    elif pattern == "concentric":
        # Use concentric loops. Defer rotation/densification until we know
        # the ownship/entry reference so we can implement a per-loop
        # "complete-one-loop-then-shrink" behavior (not a stitched spiral).
        if loops:
            raw_loops = loops
            used_loops = True
        else:
            # fall back to scanline only if no loops could be generated at all
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
            loop_anchor = centroid_local
            prev_raw_loop: Optional[List[_LocalPoint]] = None
            prev_dense_loop: Optional[List[_LocalPoint]] = None
            raw_loops_list = list(raw_loops)
            for idx, loop in enumerate(raw_loops_list):
                if not loop:
                    continue
                # --- Anchor transition: extend previous loop's last edge to ---
                # --- intersect current loop's first edge for smooth join. ---
                rot_ref = loop_anchor
                if prev_raw_loop is not None and prev_dense_loop is not None:
                    anchor_pt, cut_idx = _compute_anchor_transition(
                        prev_raw_loop, loop, prev_dense_loop, loop_anchor)
                    if anchor_pt is not None and cut_idx >= 0:
                        modified = prev_dense_loop[:cut_idx + 1] + [anchor_pt, prev_dense_loop[0]]
                        prepared_candidate_paths[-1] = modified
                        # anchor_pt is collinear with V_s→V_{s+1} by
                        # construction; start the next loop at V_{s+1}.
                        n_curr = len(loop)
                        s = min(range(n_curr), key=lambda k:
                                _distance_m(loop[k].x - loop_anchor.x, loop[k].y - loop_anchor.y))
                        vb = loop[(s + 1) % n_curr]
                        rot_ref = vb

                # densify the raw loop, then rotate to start nearest to
                # rot_ref (V_{s+1} or loop_anchor).
                loop_closed = list(loop) + ([loop[0]] if len(loop) >= 1 and _distance_m(loop[0].x - loop[-1].x, loop[0].y - loop[-1].y) > 1e-6 else [])
                dense_raw = _densify_path(loop_closed or list(loop), max_step_m=dense_step)
                if not dense_raw:
                    continue
                dense_rotated = _rotate_path_to_nearest(dense_raw, rot_ref)
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
                # Save raw and dense for the next loop's anchor transition.
                prev_raw_loop = loop
                prev_dense_loop = dense_rotated_closed
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

                # Decide direction: outside-in (outer→inner) or inside-out.
                # Compare distance to the outermost loop vs the centroid;
                # whichever is closer determines the start direction.
                outer_loop = raw_loops[0]
                dist_outer = min(
                    _distance_m(outer_loop[k].x - ownship_local.x, outer_loop[k].y - ownship_local.y)
                    for k in range(len(outer_loop))
                )
                xs = [p.x for p in local_polygon]
                ys = [p.y for p in local_polygon]
                cx = sum(xs) / len(xs)
                cy = sum(ys) / len(ys)
                dist_center = _distance_m(ownship_local.x - cx, ownship_local.y - cy)
                # Use inside-out when ownship is clearly closer to the centre
                use_inside_out = dist_center < dist_outer * 0.8
            else:
                entry_point = _build_polygon_entry_point(local_polygon, ref_lon, ref_lat, ownship_point)
                start_point = entry_point
                entry_local = _project_point_to_local(entry_point, ref_lon=ref_lon, ref_lat=ref_lat)
                anchor_local = entry_local
                if _distance_m(entry_local.x - ownship_local.x, entry_local.y - ownship_local.y) > 1e-6:
                    approach_heading_deg = _bearing_from_vector(entry_local.x - ownship_local.x, entry_local.y - ownship_local.y)
                else:
                    approach_heading_deg = ownship_heading_deg
                use_inside_out = False

            # Determine loop iteration order.
            # Outside-in:  [outermost, ..., innermost] — ownship joins at outer ring.
            # Inside-out:  [innermost, ..., outermost] — ownship starts at inner ring.
            loop_iter = reversed(raw_loops) if use_inside_out else raw_loops

            # For each concentric loop, rotate so the vertex nearest to the
            # current anchor becomes the start, close the loop (return to
            # start), then densify and filter.  After the first loop the
            # anchor is updated to the previous loop's tail so adjacent
            # loops transition smoothly (no jumps).
            loop_anchor = anchor_local
            prev_raw_loop: Optional[List[_LocalPoint]] = None
            prev_dense_loop: Optional[List[_LocalPoint]] = None
            loops_list = list(loop_iter)
            for idx, loop in enumerate(loops_list):
                if not loop:
                    continue
                # --- Anchor transition: extend previous loop's last edge to ---
                # --- intersect current loop's first edge for smooth join. ---
                rot_ref = loop_anchor
                if prev_raw_loop is not None and prev_dense_loop is not None:
                    anchor_pt, cut_idx = _compute_anchor_transition(
                        prev_raw_loop, loop, prev_dense_loop, loop_anchor)
                    if anchor_pt is not None and cut_idx >= 0:
                        modified = prev_dense_loop[:cut_idx + 1] + [anchor_pt, prev_dense_loop[0]]
                        prepared_candidate_paths[-1] = modified
                        # anchor_pt is collinear with V_s→V_{s+1} by
                        # construction; start the next loop at V_{s+1}.
                        n_curr = len(loop)
                        s = min(range(n_curr), key=lambda k:
                                _distance_m(loop[k].x - loop_anchor.x, loop[k].y - loop_anchor.y))
                        vb = loop[(s + 1) % n_curr]
                        rot_ref = vb

                # densify the raw loop, then rotate to start nearest to
                # rot_ref (V_{s+1} or loop_anchor).
                loop_closed = list(loop) + ([loop[0]] if len(loop) >= 1 and _distance_m(loop[0].x - loop[-1].x, loop[0].y - loop[-1].y) > 1e-6 else [])
                dense_raw = _densify_path(loop_closed or list(loop), max_step_m=dense_step)
                if not dense_raw:
                    continue
                dense_rotated = _rotate_path_to_nearest(dense_raw, rot_ref)
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
                # Save raw and dense for the next loop's anchor transition.
                prev_raw_loop = loop
                prev_dense_loop = dense_rotated_closed

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
            def _score(points: List[_LocalPoint]) -> float:
                return _compute_start_cost(
                    points=points,
                    ownship_point=ownship_local,
                    ownship_heading_deg=ownship_heading_deg,
                    turn_penalty_m_per_deg=turn_penalty,
                ) + endpoint_weight * _compute_endpoint_distance(
                    points=points,
                    target_point=ownship_local,
                )

            if _point_in_polygon((ownship_local.x, ownship_local.y), polygon_xy):
                start_point = ownship_point
                inside_start_variants: List[List[_LocalPoint]] = []
                for path in prepared_candidate_paths:
                    inside_start_variants.extend(_build_inside_start_variants(path))
                if inside_start_variants:
                    prepared_candidate_paths = inside_start_variants
                selected_path = min(
                    prepared_candidate_paths,
                    key=_score,
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
                        _score(points),
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

        # Simplify: straight edges need only their endpoints, not every
        # densified step. Keep only corners (vertices / anchors).
        selected_path = _simplify_collinear_path(selected_path, eps=1.0)

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
