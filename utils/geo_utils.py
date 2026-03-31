from math import radians, sin, cos, sqrt, atan2
from typing import List

from domain.models import GeoPoint


EARTH_RADIUS_M = 6371000.0


def haversine_distance_m(p1: GeoPoint, p2: GeoPoint) -> float:
    """
    计算两经纬度点之间的大圆距离，单位：米
    """
    lat1 = radians(p1.latitude)
    lon1 = radians(p1.longitude)
    lat2 = radians(p2.latitude)
    lon2 = radians(p2.longitude)

    dlat = lat2 - lat1
    dlon = lon2 - lon1

    a = sin(dlat / 2) ** 2 + cos(lat1) * cos(lat2) * sin(dlon / 2) ** 2
    c = 2 * atan2(sqrt(a), sqrt(1 - a))
    return EARTH_RADIUS_M * c


def is_point_in_polygon(point: GeoPoint, polygon: List[GeoPoint]) -> bool:
    """
    射线法判断点是否在多边形内
    这里用 (longitude, latitude) 作为平面坐标近似判断，适合当前小区域测试
    """
    x = point.longitude
    y = point.latitude

    inside = False
    n = len(polygon)

    for i in range(n):
        j = (i - 1) % n
        xi, yi = polygon[i].longitude, polygon[i].latitude
        xj, yj = polygon[j].longitude, polygon[j].latitude

        intersects = ((yi > y) != (yj > y)) and (
            x < (xj - xi) * (y - yi) / ((yj - yi) + 1e-12) + xi
        )
        if intersects:
            inside = not inside

    return inside