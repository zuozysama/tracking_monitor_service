import os
from pathlib import Path
from typing import Any, Dict, Optional

import yaml
from pydantic import BaseModel, Field


class FixedTrackingConfig(BaseModel):
    default_region_radius_m: float = 3000.0


class TrackingArrivalConfig(BaseModel):
    tolerance_m: float = 50.0
    stable_cycles: int = 3
    heading_tolerance_deg: float = 15.0
    speed_tolerance_kn: float = 2.0


class TrackingFilterConfig(BaseModel):
    min_target_range_m: float = 0.0
    max_target_range_m: float = 8000.0
    bearing_center_deg: float = 0.0
    bearing_window_deg: float = 360.0

    target_id_weight: float = 100.0
    batch_id_weight: float = 60.0
    hull_number_weight: float = 60.0
    target_type_weight: float = 20.0
    target_type_preferred_weight: float = 15.0
    enemy_friend_weight: float = 15.0
    enemy_friend_preferred_weight: float = 10.0
    military_civil_weight: float = 15.0
    military_civil_preferred_weight: float = 10.0
    range_score_weight: float = 1.0
    bearing_score_weight: float = 0.5
    threat_score_weight: float = 30.0
    value_score_weight: float = 20.0

    threat_level_max: float = 5.0
    default_target_type_value_score: float = 0.0
    default_military_civil_value_score: float = 0.0
    target_type_value_scores: Dict[int, float] = Field(default_factory=dict)
    military_civil_value_scores: Dict[int, float] = Field(default_factory=dict)

    sector_filter_enabled: bool = True
    sector_center_deg: float = 0.0
    sector_width_deg: float = 120.0

    top_k_candidates: int = 1
    hysteresis_enabled: bool = True
    hysteresis_margin: float = 0.5
    debug_enabled: bool = True


class TrackingConfig(BaseModel):
    target_lost_timeout_sec: int = 30
    escort_distance_m: float = 300.0
    intercept_distance_m: float = 500.0
    expel_distance_m: float = 200.0
    filter: TrackingFilterConfig = TrackingFilterConfig()
    arrival: TrackingArrivalConfig = TrackingArrivalConfig()


class CollaborationConfig(BaseModel):
    optical_post_retry_interval_sec: int = 1
    sonar_poll_interval_sec: int = 5


class ExternalServiceEndpointConfig(BaseModel):
    mode: str = "mock"
    base_url: str = ""
    timeout_sec: float = 3.0


class ExternalServicesConfig(BaseModel):
    optronic: ExternalServiceEndpointConfig = ExternalServiceEndpointConfig()
    media: ExternalServiceEndpointConfig = ExternalServiceEndpointConfig()
    planning: ExternalServiceEndpointConfig = ExternalServiceEndpointConfig()
    sonar: ExternalServiceEndpointConfig = ExternalServiceEndpointConfig()
    autonomy: ExternalServiceEndpointConfig = ExternalServiceEndpointConfig()


class ServiceConfig(BaseModel):
    fixed_tracking: FixedTrackingConfig = FixedTrackingConfig()
    tracking: TrackingConfig = TrackingConfig()
    collaboration: CollaborationConfig = CollaborationConfig()
    external_services: ExternalServicesConfig = ExternalServicesConfig()


def _deep_merge(base: Dict[str, Any], override: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(base)
    for key, value in override.items():
        if key in result and isinstance(result[key], dict) and isinstance(value, dict):
            result[key] = _deep_merge(result[key], value)
        else:
            result[key] = value
    return result


def _default_settings_dict() -> Dict[str, Any]:
    return ServiceConfig().model_dump()


def _load_yaml_dict(config_path: Path) -> Dict[str, Any]:
    if not config_path.exists():
        return {}

    with config_path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}

    if not isinstance(data, dict):
        raise ValueError("yaml root must be a mapping/dict")

    return data


def _get_env_str(name: str) -> Optional[str]:
    value = os.getenv(name)
    if value is None:
        return None
    value = value.strip()
    return value if value else None


def _get_env_float(name: str) -> Optional[float]:
    value = _get_env_str(name)
    if value is None:
        return None
    try:
        return float(value)
    except Exception:
        return None


def _apply_external_service_env_overrides(merged: Dict[str, Any]) -> Dict[str, Any]:
    result = dict(merged)
    external_services = dict(result.get("external_services") or {})

    service_names = ["optronic", "media", "planning", "sonar", "autonomy"]
    for service_name in service_names:
        section = dict(external_services.get(service_name) or {})
        prefix = f"EXTERNAL_{service_name.upper()}"

        mode = _get_env_str(f"{prefix}_MODE")
        if mode is not None:
            section["mode"] = mode

        base_url = _get_env_str(f"{prefix}_BASE_URL")
        if base_url is not None:
            section["base_url"] = base_url

        timeout_sec = _get_env_float(f"{prefix}_TIMEOUT_SEC")
        if timeout_sec is not None:
            section["timeout_sec"] = timeout_sec

        external_services[service_name] = section

    result["external_services"] = external_services
    return result


def load_settings(config_file: str = "config/service_settings.yaml") -> ServiceConfig:
    config_path = Path(config_file)
    default_dict = _default_settings_dict()
    yaml_dict = _load_yaml_dict(config_path)
    merged = _deep_merge(default_dict, yaml_dict)
    merged = _apply_external_service_env_overrides(merged)
    return ServiceConfig(**merged)


settings = load_settings()
