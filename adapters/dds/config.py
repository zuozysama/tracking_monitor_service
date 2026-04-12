import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml


@dataclass(frozen=True)
class DdsRuntimeConfig:
    mode: str
    platform: str
    domain_id: int
    qos_file: str
    license_file: str
    participant_name: str


def _read_yaml_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    with path.open("r", encoding="utf-8") as fp:
        data = yaml.safe_load(fp) or {}
    if not isinstance(data, dict):
        return {}
    return data


def load_dds_runtime_config() -> DdsRuntimeConfig:
    cfg_path = Path(os.getenv("DDS_CONFIG_PATH", "config/dds_settings.yaml"))
    yaml_cfg = _read_yaml_config(cfg_path)
    runtime_cfg = yaml_cfg.get("runtime", {}) if isinstance(yaml_cfg.get("runtime"), dict) else {}

    mode = os.getenv("DDS_MODE", str(runtime_cfg.get("mode", "mock"))).strip().lower()
    platform = os.getenv("DDS_PLATFORM", str(runtime_cfg.get("platform", "win"))).strip().lower()
    domain_id = int(os.getenv("DDS_DOMAIN_ID", runtime_cfg.get("domain_id", 0)))
    qos_file = os.getenv("DDS_QOS_FILE", str(runtime_cfg.get("qos_file", "config/dds_qos.xml")))
    license_file = os.getenv("DDS_LICENSE_FILE", str(runtime_cfg.get("license_file", "")))
    participant_name = os.getenv(
        "DDS_PARTICIPANT_NAME",
        str(runtime_cfg.get("participant_name", "cc_me_tracking_monitor_service")),
    )

    return DdsRuntimeConfig(
        mode=mode,
        platform=platform,
        domain_id=domain_id,
        qos_file=qos_file,
        license_file=license_file,
        participant_name=participant_name,
    )
