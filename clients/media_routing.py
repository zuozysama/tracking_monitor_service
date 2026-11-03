"""Internal evidence routing; independent of optical command/status fields."""

from __future__ import annotations

from math import atan2, cos, degrees, isfinite, radians, sin

FRONT_CHANNEL = "front_recognition"
REAR_CHANNEL = "rear_recognition"


def channel_from_relative_bearing(angle: float) -> str:
    angle = angle % 360.0
    return REAR_CHANNEL if 90.0 <= angle < 270.0 else FRONT_CHANNEL


def select_evidence_channel(ownship, target) -> str | None:
    if ownship is None or target is None:
        return None
    values = (ownship.longitude, ownship.latitude, ownship.heading_deg,
              target.longitude, target.latitude)
    if any(value is None or not isfinite(float(value)) for value in values):
        return None
    lon1, lat1, heading, lon2, lat2 = map(float, values)
    lat1, lat2 = radians(lat1), radians(lat2)
    delta_lon = radians(lon2 - lon1)
    x = sin(delta_lon) * cos(lat2)
    y = cos(lat1) * sin(lat2) - sin(lat1) * cos(lat2) * cos(delta_lon)
    if abs(x) + abs(y) < 1e-12:
        return None
    bearing = degrees(atan2(x, y)) % 360.0
    return channel_from_relative_bearing(bearing - heading)
