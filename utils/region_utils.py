from typing import Optional

from domain.models import GeoPoint, TargetState, TaskArea
from utils.geo_utils import haversine_distance_m, is_point_in_polygon


def is_point_in_task_area(point: GeoPoint, task_area: Optional[TaskArea]) -> bool:
    if task_area is None:
        return True

    if task_area.area_type == "polygon":
        if not task_area.points:
            return False
        return is_point_in_polygon(point, task_area.points)

    if task_area.area_type == "route":
        # route area does not define corridor width in current contract,
        # keep historical behavior: only polygon is used for in-area filtering.
        return True

    if task_area.area_type == "circle":
        if task_area.center is None or task_area.radius_m is None:
            return False
        return haversine_distance_m(point, task_area.center) <= task_area.radius_m

    return False


def is_target_in_task_area(
    target: TargetState,
    task_area: Optional[TaskArea],
) -> bool:
    """
    判断目标是否位于任务区域内。
    若 task_area 为空，则默认通过。
    """
    if task_area is None:
        return True

    point = GeoPoint(
        longitude=target.longitude,
        latitude=target.latitude,
    )
    return is_point_in_task_area(point, task_area)
