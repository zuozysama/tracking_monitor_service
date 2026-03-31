from typing import Optional

from domain.models import GeoPoint, TargetState, TaskArea
from utils.geo_utils import is_point_in_polygon


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
    return is_point_in_polygon(point, task_area.points)
