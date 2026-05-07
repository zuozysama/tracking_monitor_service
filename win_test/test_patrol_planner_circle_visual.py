from __future__ import annotations

import csv
import json
import math
import sys
from datetime import datetime
from pathlib import Path
from typing import Sequence


ROOT_DIR = Path(__file__).resolve().parents[1]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from algorithms.patrol_planner import generate_simple_patrol_waypoints
from domain.models import GeoPoint, TaskArea


# Edit these values to preview different circle patrol plans.
PATROL_NUM_PASSES = 8
PATROL_SCAN_RADIUS_M: float | None = 1000.0
PATROL_BOUNDARY_CLEARANCE_M: float | None = 50.0
EXPECTED_SPEED = 12.0

CIRCLE_CENTER_LONGITUDE = 124.3819
CIRCLE_CENTER_LATITUDE = 21.3589
CIRCLE_RADIUS_M = 5000.0

# Put ownship inside or outside the circle to compare current planner behavior.
OWNSHIP_LONGITUDE = 124.30
OWNSHIP_LATITUDE = 21.30
OWNSHIP_HEADING_DEG: float | None = 0.0

LABEL_WAYPOINTS = True
DRAW_SCAN_RADIUS_CIRCLES = True
DRAW_RADIUS_TO_OWNSHIP = True
OUTPUT_DIR = Path(__file__).resolve().parent / "output"


EARTH_RADIUS_M = 6371000.0


def main() -> None:
    center = GeoPoint(longitude=CIRCLE_CENTER_LONGITUDE, latitude=CIRCLE_CENTER_LATITUDE)
    ownship_point = GeoPoint(longitude=OWNSHIP_LONGITUDE, latitude=OWNSHIP_LATITUDE)
    task_area = TaskArea(area_type="circle", center=center, radius_m=CIRCLE_RADIUS_M)

    waypoints = generate_simple_patrol_waypoints(
        task_area=task_area,
        expected_speed=EXPECTED_SPEED,
        num_passes=PATROL_NUM_PASSES,
        ownship_point=ownship_point,
        ownship_heading_deg=OWNSHIP_HEADING_DEG,
        scan_radius_m=PATROL_SCAN_RADIUS_M,
        boundary_clearance_m=PATROL_BOUNDARY_CLEARANCE_M,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    stem = f"circle_patrol_plan_{timestamp}"
    run_output_dir = OUTPUT_DIR / stem
    run_output_dir.mkdir(parents=True, exist_ok=True)

    circle_points = build_circle_points(center, CIRCLE_RADIUS_M, count=144)
    all_geo_points = circle_points + [center, ownship_point] + [
        GeoPoint(longitude=point.longitude, latitude=point.latitude) for point in waypoints
    ]
    projector = LocalProjector(all_geo_points)
    circle_xy = [projector.to_xy(point) for point in circle_points]
    center_xy = projector.to_xy(center)
    ownship_xy = projector.to_xy(ownship_point)
    waypoint_xy = [projector.to_xy(GeoPoint(longitude=point.longitude, latitude=point.latitude)) for point in waypoints]

    write_waypoints_csv(run_output_dir / "waypoints.csv", waypoints, projector)
    write_summary_json(run_output_dir / "summary.json", center, ownship_point, waypoints)
    write_svg(run_output_dir / "plan.svg", circle_xy, center_xy, ownship_xy, waypoint_xy, waypoints)
    png_path = try_write_png(run_output_dir / "plan.png", circle_xy, center_xy, ownship_xy, waypoint_xy, waypoints)

    print(f"Generated {len(waypoints)} circle patrol waypoints.")
    print(f"Ownship inside circle: {is_ownship_inside_circle(center, ownship_point, CIRCLE_RADIUS_M)}")
    print(f"Output: {run_output_dir}")
    print(f"CSV: {run_output_dir / 'waypoints.csv'}")
    print(f"SVG: {run_output_dir / 'plan.svg'}")
    if png_path is not None:
        print(f"PNG: {png_path}")
    else:
        print("PNG: skipped because matplotlib is not installed; SVG was generated.")


class LocalProjector:
    def __init__(self, points: Sequence[GeoPoint]) -> None:
        self.ref_lon = sum(point.longitude for point in points) / len(points)
        self.ref_lat = sum(point.latitude for point in points) / len(points)
        self.ref_lat_rad = math.radians(self.ref_lat)

    def to_xy(self, point: GeoPoint) -> tuple[float, float]:
        x = math.radians(point.longitude - self.ref_lon) * EARTH_RADIUS_M * math.cos(self.ref_lat_rad)
        y = math.radians(point.latitude - self.ref_lat) * EARTH_RADIUS_M
        return x, y


def build_circle_points(center: GeoPoint, radius_m: float, count: int) -> list[GeoPoint]:
    lat_rad = math.radians(center.latitude)
    cos_lat = max(math.cos(lat_rad), 1e-12)
    points = []
    for index in range(count):
        angle = 2.0 * math.pi * index / count
        dx = radius_m * math.cos(angle)
        dy = radius_m * math.sin(angle)
        points.append(
            GeoPoint(
                longitude=center.longitude + math.degrees(dx / (EARTH_RADIUS_M * cos_lat)),
                latitude=center.latitude + math.degrees(dy / EARTH_RADIUS_M),
            )
        )
    return points


def write_waypoints_csv(path: Path, waypoints: Sequence[object], projector: LocalProjector) -> None:
    with path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(["index", "longitude", "latitude", "x_m", "y_m", "expected_speed"])
        for index, waypoint in enumerate(waypoints):
            point = GeoPoint(longitude=waypoint.longitude, latitude=waypoint.latitude)
            x, y = projector.to_xy(point)
            writer.writerow([index, waypoint.longitude, waypoint.latitude, round(x, 3), round(y, 3), waypoint.expected_speed])


def write_summary_json(path: Path, center: GeoPoint, ownship_point: GeoPoint, waypoints: Sequence[object]) -> None:
    payload = {
        "parameters": {
            "PATROL_NUM_PASSES": PATROL_NUM_PASSES,
            "PATROL_SCAN_RADIUS_M": PATROL_SCAN_RADIUS_M,
            "PATROL_BOUNDARY_CLEARANCE_M": PATROL_BOUNDARY_CLEARANCE_M,
            "EXPECTED_SPEED": EXPECTED_SPEED,
            "CIRCLE_RADIUS_M": CIRCLE_RADIUS_M,
        },
        "center": {"longitude": center.longitude, "latitude": center.latitude},
        "ownship": {
            "longitude": ownship_point.longitude,
            "latitude": ownship_point.latitude,
            "heading_deg": OWNSHIP_HEADING_DEG,
            "inside_circle": is_ownship_inside_circle(center, ownship_point, CIRCLE_RADIUS_M),
        },
        "waypoint_count": len(waypoints),
        "route_length_m": round(route_length_m(waypoints), 3),
        "waypoints": [
            {
                "index": index,
                "longitude": waypoint.longitude,
                "latitude": waypoint.latitude,
                "expected_speed": waypoint.expected_speed,
            }
            for index, waypoint in enumerate(waypoints)
        ],
    }
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def try_write_png(
    path: Path,
    circle_xy: Sequence[tuple[float, float]],
    center_xy: tuple[float, float],
    ownship_xy: tuple[float, float],
    waypoint_xy: Sequence[tuple[float, float]],
    waypoints: Sequence[object],
) -> Path | None:
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except Exception:
        return None

    fig, ax = plt.subplots(figsize=(12, 8), dpi=160)
    closed_circle = list(circle_xy) + [circle_xy[0]]
    ax.plot([point[0] for point in closed_circle], [point[1] for point in closed_circle], color="#1f2937", linewidth=2, label="task circle")
    ax.fill([point[0] for point in closed_circle], [point[1] for point in closed_circle], color="#dbeafe", alpha=0.25)

    if waypoint_xy:
        if DRAW_SCAN_RADIUS_CIRCLES and PATROL_SCAN_RADIUS_M:
            for x, y in waypoint_xy:
                circle = plt.Circle((x, y), PATROL_SCAN_RADIUS_M, color="#22c55e", fill=False, alpha=0.08, linewidth=0.8)
                ax.add_patch(circle)
        ax.plot([point[0] for point in waypoint_xy], [point[1] for point in waypoint_xy], color="#ef4444", linewidth=1.8, label="patrol route")
        ax.scatter([point[0] for point in waypoint_xy], [point[1] for point in waypoint_xy], color="#ef4444", s=24)
        ax.scatter([waypoint_xy[0][0]], [waypoint_xy[0][1]], color="#f59e0b", edgecolors="#111827", s=85, zorder=5)
        if LABEL_WAYPOINTS:
            for index, (x, y) in enumerate(waypoint_xy):
                ax.annotate(str(index), (x, y), textcoords="offset points", xytext=(4, 4), fontsize=8)

    ax.scatter([center_xy[0]], [center_xy[1]], marker="x", color="#111827", s=90, label="circle center")
    ax.scatter([ownship_xy[0]], [ownship_xy[1]], marker="*", color="#2563eb", edgecolors="#111827", s=180, zorder=6, label="ownship")
    draw_heading_arrow_matplotlib(ax, ownship_xy)
    if DRAW_RADIUS_TO_OWNSHIP:
        ax.plot([center_xy[0], ownship_xy[0]], [center_xy[1], ownship_xy[1]], color="#2563eb", linestyle="--", alpha=0.35)

    ax.set_title(title_text(len(waypoints), route_length_m(waypoints)))
    ax.set_xlabel("local east/west meters")
    ax.set_ylabel("local north/south meters")
    ax.grid(True, linestyle="--", alpha=0.25)
    ax.set_aspect("equal", adjustable="box")
    ax.legend(loc="best")
    fig.tight_layout()
    fig.savefig(path)
    plt.close(fig)
    return path


def write_svg(
    path: Path,
    circle_xy: Sequence[tuple[float, float]],
    center_xy: tuple[float, float],
    ownship_xy: tuple[float, float],
    waypoint_xy: Sequence[tuple[float, float]],
    waypoints: Sequence[object],
) -> None:
    bounds = padded_bounds(list(circle_xy) + [center_xy, ownship_xy] + list(waypoint_xy), CIRCLE_RADIUS_M * 0.08)
    mapper = SvgMapper(bounds, width=1400, height=900, padding=70)
    circle_points = " ".join(mapper.point(xy) for xy in circle_xy)
    route_points = " ".join(mapper.point(xy) for xy in waypoint_xy)

    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" width="1400" height="900" viewBox="0 0 1400 900">',
        '<rect width="100%" height="100%" fill="#f8fafc"/>',
        f'<text x="70" y="38" font-family="Arial" font-size="20" fill="#111827">{escape_xml(title_text(len(waypoints), route_length_m(waypoints)))}</text>',
        '<g font-family="Arial" font-size="12">',
        f'<polygon points="{circle_points}" fill="#dbeafe" fill-opacity="0.38" stroke="#1f2937" stroke-width="3"/>',
    ]

    if route_points:
        if DRAW_SCAN_RADIUS_CIRCLES and PATROL_SCAN_RADIUS_M:
            svg_radius = PATROL_SCAN_RADIUS_M * mapper.scale
            for xy in waypoint_xy:
                cx, cy = mapper.xy(xy)
                parts.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{svg_radius:.2f}" fill="none" stroke="#22c55e" stroke-opacity="0.10" stroke-width="1"/>')
        parts.append(f'<polyline points="{route_points}" fill="none" stroke="#ef4444" stroke-width="3" stroke-linejoin="round"/>')
        for index, xy in enumerate(waypoint_xy):
            cx, cy = mapper.xy(xy)
            radius = 7 if index == 0 else 4
            fill = "#f59e0b" if index == 0 else "#ef4444"
            stroke = ' stroke="#111827" stroke-width="1.5"' if index == 0 else ""
            parts.append(f'<circle cx="{cx:.2f}" cy="{cy:.2f}" r="{radius}" fill="{fill}"{stroke}/>')
            if LABEL_WAYPOINTS:
                parts.append(f'<text x="{cx + 8:.2f}" y="{cy - 8:.2f}" fill="#374151">{index}</text>')

    cx, cy = mapper.xy(center_xy)
    parts.append(f'<line x1="{cx - 8:.2f}" y1="{cy - 8:.2f}" x2="{cx + 8:.2f}" y2="{cy + 8:.2f}" stroke="#111827" stroke-width="2"/>')
    parts.append(f'<line x1="{cx - 8:.2f}" y1="{cy + 8:.2f}" x2="{cx + 8:.2f}" y2="{cy - 8:.2f}" stroke="#111827" stroke-width="2"/>')
    ox, oy = mapper.xy(ownship_xy)
    parts.append(star_svg(ox, oy, 13, "#2563eb", "#111827"))
    parts.extend(heading_arrow_svg(mapper, ownship_xy))

    parts.append("</g></svg>")
    path.write_text("\n".join(parts), encoding="utf-8")


class SvgMapper:
    def __init__(self, bounds: tuple[float, float, float, float], width: int, height: int, padding: int) -> None:
        min_x, min_y, max_x, max_y = bounds
        span_x = max(max_x - min_x, 1.0)
        span_y = max(max_y - min_y, 1.0)
        self.min_x = min_x
        self.min_y = min_y
        self.max_y = max_y
        self.scale = min((width - padding * 2) / span_x, (height - padding * 2) / span_y)
        self.padding = padding

    def xy(self, point: tuple[float, float]) -> tuple[float, float]:
        x, y = point
        return self.padding + (x - self.min_x) * self.scale, self.padding + (self.max_y - y) * self.scale

    def point(self, point: tuple[float, float]) -> str:
        x, y = self.xy(point)
        return f"{x:.2f},{y:.2f}"


def padded_bounds(points: Sequence[tuple[float, float]], extra_padding_m: float) -> tuple[float, float, float, float]:
    min_x = min(point[0] for point in points)
    max_x = max(point[0] for point in points)
    min_y = min(point[1] for point in points)
    max_y = max(point[1] for point in points)
    padding = max(max(max_x - min_x, max_y - min_y, 1.0) * 0.08, extra_padding_m)
    return min_x - padding, min_y - padding, max_x + padding, max_y + padding


def draw_heading_arrow_matplotlib(ax: object, ownship_xy: tuple[float, float]) -> None:
    if OWNSHIP_HEADING_DEG is None:
        return
    arrow_len = max(CIRCLE_RADIUS_M * 0.12, 300.0)
    dx = math.sin(math.radians(OWNSHIP_HEADING_DEG)) * arrow_len
    dy = math.cos(math.radians(OWNSHIP_HEADING_DEG)) * arrow_len
    ax.arrow(ownship_xy[0], ownship_xy[1], dx, dy, color="#2563eb", width=arrow_len * 0.025, length_includes_head=True)


def heading_arrow_svg(mapper: SvgMapper, ownship_xy: tuple[float, float]) -> list[str]:
    if OWNSHIP_HEADING_DEG is None:
        return []
    arrow_len = max(CIRCLE_RADIUS_M * 0.12, 300.0)
    dx = math.sin(math.radians(OWNSHIP_HEADING_DEG)) * arrow_len
    dy = math.cos(math.radians(OWNSHIP_HEADING_DEG)) * arrow_len
    start_x, start_y = mapper.xy(ownship_xy)
    end_x, end_y = mapper.xy((ownship_xy[0] + dx, ownship_xy[1] + dy))
    return [
        '<defs><marker id="arrowhead" markerWidth="10" markerHeight="7" refX="9" refY="3.5" orient="auto">'
        '<polygon points="0 0, 10 3.5, 0 7" fill="#2563eb"/></marker></defs>',
        f'<line x1="{start_x:.2f}" y1="{start_y:.2f}" x2="{end_x:.2f}" y2="{end_y:.2f}" stroke="#2563eb" stroke-width="4" marker-end="url(#arrowhead)"/>',
    ]


def route_length_m(waypoints: Sequence[object]) -> float:
    total = 0.0
    for current, nxt in zip(waypoints, waypoints[1:]):
        total += haversine_m(current.latitude, current.longitude, nxt.latitude, nxt.longitude)
    return total


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2.0) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2.0) ** 2
    return 2.0 * EARTH_RADIUS_M * math.atan2(math.sqrt(a), math.sqrt(max(1.0 - a, 1e-12)))


def is_ownship_inside_circle(center: GeoPoint, ownship_point: GeoPoint, radius_m: float) -> bool:
    return haversine_m(center.latitude, center.longitude, ownship_point.latitude, ownship_point.longitude) <= radius_m


def title_text(waypoint_count: int, length_m: float) -> str:
    inside = is_ownship_inside_circle(
        GeoPoint(longitude=CIRCLE_CENTER_LONGITUDE, latitude=CIRCLE_CENTER_LATITUDE),
        GeoPoint(longitude=OWNSHIP_LONGITUDE, latitude=OWNSHIP_LATITUDE),
        CIRCLE_RADIUS_M,
    )
    return (
        f"Circle patrol preview | waypoints={waypoint_count} | length={length_m / 1000:.2f} km | "
        f"radius={CIRCLE_RADIUS_M:.0f} m | scan_radius={PATROL_SCAN_RADIUS_M} | "
        f"clearance={PATROL_BOUNDARY_CLEARANCE_M} | ownship_inside={inside}"
    )


def star_svg(cx: float, cy: float, radius: float, fill: str, stroke: str) -> str:
    points = []
    for idx in range(10):
        angle = -math.pi / 2 + idx * math.pi / 5
        r = radius if idx % 2 == 0 else radius * 0.45
        points.append(f"{cx + math.cos(angle) * r:.2f},{cy + math.sin(angle) * r:.2f}")
    return f'<polygon points="{" ".join(points)}" fill="{fill}" stroke="{stroke}" stroke-width="1.5"/>'


def escape_xml(text: str) -> str:
    return text.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


if __name__ == "__main__":
    main()
