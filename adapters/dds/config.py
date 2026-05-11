import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DdsRuntimeConfig:
    mode: str
    platform: str
    domain_id: int
    qos_file: str
    qos_profile: str
    license_file: str
    participant_name: str
    topic_qos_profiles: dict[str, str] = field(default_factory=dict)


def _read_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or {}
    if not isinstance(data, dict):
        return {}
    return data


def normalize_dds_qos_profile(value: str, default: str = "BestEffort") -> str:
    normalized = str(value or "").strip().lower().replace("-", "_")
    if normalized in {"reliable", "default_reliable"}:
        return "Reliable"
    if normalized in {"besteffort", "best_effort", "default_besteffort", "default_best_effort"}:
        return "BestEffort"
    return default


def _load_topic_qos_profiles(default_profile: str) -> dict[str, str]:
    from domain.dds_contract import (
        ELECTRO_OPTICAL_LINKAGE_CMD_TOPIC,
        MANUAL_SELECTION_REQUEST_TOPIC,
        MANUAL_SWITCH_REQUEST_TOPIC,
        OWNSHIP_NAVIGATION_TOPIC,
        PREPLAN_RESULT_TOPIC,
        STREAM_MEDIA_PARAM_TOPIC,
        TARGET_PERCEPTION_TOPIC,
        TASK_UPDATE_TOPIC,
    )

    topic_env_keys = {
        TASK_UPDATE_TOPIC: "DDS_QOS_PROFILE_TASK_UPDATE",
        PREPLAN_RESULT_TOPIC: "DDS_QOS_PROFILE_PREPLAN_RESULT",
        MANUAL_SELECTION_REQUEST_TOPIC: "DDS_QOS_PROFILE_MANUAL_SELECTION_REQUEST",
        MANUAL_SWITCH_REQUEST_TOPIC: "DDS_QOS_PROFILE_MANUAL_SWITCH_REQUEST",
        ELECTRO_OPTICAL_LINKAGE_CMD_TOPIC: "DDS_QOS_PROFILE_ELECTRO_OPTICAL_LINKAGE_CMD",
        STREAM_MEDIA_PARAM_TOPIC: "DDS_QOS_PROFILE_STREAM_MEDIA_PARAM",
        OWNSHIP_NAVIGATION_TOPIC: "DDS_QOS_PROFILE_OWNSHIP_NAVIGATION",
        TARGET_PERCEPTION_TOPIC: "DDS_QOS_PROFILE_TARGET_PERCEPTION",
    }

    profiles: dict[str, str] = {}
    for topic, env_key in topic_env_keys.items():
        env_value = os.getenv(env_key, "").strip()
        if env_value:
            profiles[topic] = normalize_dds_qos_profile(env_value, default_profile)
    return profiles


def load_dds_runtime_config() -> DdsRuntimeConfig:
    cfg_path = Path(os.getenv("DDS_CONFIG_PATH", "config/dds_settings.yaml"))
    yaml_cfg = _read_yaml_config(cfg_path)
    runtime_cfg = yaml_cfg.get("runtime", {}) if isinstance(yaml_cfg.get("runtime"), dict) else {}

    mode = os.getenv("DDS_MODE", str(runtime_cfg.get("mode", "mock"))).strip().lower()
    platform = os.getenv("DDS_PLATFORM", str(runtime_cfg.get("platform", "win"))).strip().lower()
    # Keep legacy value compatible with current Linux runtime naming.
    if platform == "ft2000":
        platform = "linux"
    domain_id = int(os.getenv("DDS_DOMAIN_ID", runtime_cfg.get("domain_id", 0)))
    qos_file = os.getenv("DDS_QOS_FILE", str(runtime_cfg.get("qos_file", "config/dds_qos.xml")))
    qos_profile = normalize_dds_qos_profile(
        os.getenv("DDS_QOS_PROFILE", str(runtime_cfg.get("qos_profile", "BestEffort"))),
    )
    topic_qos_profiles = _load_topic_qos_profiles(qos_profile)
    license_file = os.getenv("DDS_LICENSE_FILE", str(runtime_cfg.get("license_file", "")))
    participant_name = os.getenv(
        "DDS_PARTICIPANT_NAME",
        str(runtime_cfg.get("participant_name", "cc_cm_tracking_monitor_service")),
    )

    return DdsRuntimeConfig(
        mode=mode,
        platform=platform,
        domain_id=domain_id,
        qos_file=qos_file,
        qos_profile=qos_profile,
        topic_qos_profiles=topic_qos_profiles,
        license_file=license_file,
        participant_name=participant_name,
    )
