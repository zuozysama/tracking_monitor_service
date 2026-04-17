import os
from pathlib import Path
from typing import Dict

import yaml

from domain.enums import FinishReason, TaskStatus, TaskType

DEFAULT_TOPIC_PREFIX = "cc_cm_tracking_monitor_service.v1."
DEFAULT_TOPIC_SUFFIXES = {
    "task_update_topic",
    "preplan_result_topic",
    "manual_selection_request_topic",
    "manual_switch_request_topic",
    "electro_optical_linkage_cmd_topic",
    "stream_media_param_topic",
    "ownship_navigation_topic",
    "target_perception_topic",
}


def _load_yaml_topics_by_suffix() -> Dict[str, str]:
    cfg_path = Path(os.getenv("DDS_CONFIG_PATH", "config/dds_settings.yaml"))
    if not cfg_path.exists():
        return {}

    try:
        with cfg_path.open("r", encoding="utf-8") as fp:
            data = yaml.safe_load(fp) or {}
    except Exception:
        return {}

    if not isinstance(data, dict):
        return {}
    topics = data.get("topics")
    if not isinstance(topics, dict):
        return {}

    resolved: Dict[str, str] = {}
    for topic_name in topics.keys():
        if not isinstance(topic_name, str):
            continue
        for suffix in DEFAULT_TOPIC_SUFFIXES:
            if topic_name.endswith(suffix):
                resolved[suffix] = topic_name
                break
    return resolved


_YAML_TOPICS_BY_SUFFIX = _load_yaml_topics_by_suffix()
TOPIC_PREFIX = os.getenv("DDS_TOPIC_PREFIX", DEFAULT_TOPIC_PREFIX).strip() or DEFAULT_TOPIC_PREFIX


def _resolve_topic(env_key: str, suffix: str) -> str:
    env_value = os.getenv(env_key, "").strip()
    if env_value:
        return env_value
    yaml_value = _YAML_TOPICS_BY_SUFFIX.get(suffix, "").strip()
    if yaml_value:
        return yaml_value
    return TOPIC_PREFIX + suffix


TASK_UPDATE_TOPIC = _resolve_topic("DDS_TOPIC_TASK_UPDATE", "task_update_topic")
PREPLAN_RESULT_TOPIC = _resolve_topic("DDS_TOPIC_PREPLAN_RESULT", "preplan_result_topic")
MANUAL_SELECTION_REQUEST_TOPIC = _resolve_topic("DDS_TOPIC_MANUAL_SELECTION_REQUEST", "manual_selection_request_topic")
MANUAL_SWITCH_REQUEST_TOPIC = _resolve_topic("DDS_TOPIC_MANUAL_SWITCH_REQUEST", "manual_switch_request_topic")
ELECTRO_OPTICAL_LINKAGE_CMD_TOPIC = _resolve_topic(
    "DDS_TOPIC_ELECTRO_OPTICAL_LINKAGE_CMD", "electro_optical_linkage_cmd_topic"
)
STREAM_MEDIA_PARAM_TOPIC = _resolve_topic("DDS_TOPIC_STREAM_MEDIA_PARAM", "stream_media_param_topic")
OWNSHIP_NAVIGATION_TOPIC = _resolve_topic("DDS_TOPIC_OWNSHIP_NAVIGATION", "ownship_navigation_topic")
TARGET_PERCEPTION_TOPIC = _resolve_topic("DDS_TOPIC_TARGET_PERCEPTION", "target_perception_topic")

TASK_TYPE_CODE_MAP = {
    TaskType.PATROL: 1,
    TaskType.ESCORT: 2,
    TaskType.INTERCEPT: 3,
    TaskType.EXPEL: 4,
    TaskType.FIXED_TRACKING: 5,
    TaskType.UNDERWATER_SEARCH: 6,
    TaskType.PREPLAN: 7,
}

TASK_STATUS_CODE_MAP = {
    TaskStatus.CREATED: 1,
    TaskStatus.RUNNING: 2,
    TaskStatus.COMPLETED: 3,
    TaskStatus.TERMINATED: 4,
    TaskStatus.ABNORMAL: 5,
    TaskStatus.WAITING_TARGET: 2,
}

FINISH_REASON_CODE_MAP = {
    None: 0,
    FinishReason.MANUAL_TERMINATED: 1,
    FinishReason.TIMEOUT: 2,
    FinishReason.TARGET_LOST: 3,
    FinishReason.COMPLETED: 4,
    FinishReason.OUT_OF_REGION: 5,
    FinishReason.SONAR_UNMATCHED: 6,
}

PHASE_CODE_MAP = {
    "planning": 1,
    "patrolling": 2,
    "target_screening": 3,
    "standby_monitoring": 4,
    "engaging": 5,
    "intercepting": 6,
    "evidence_collecting": 7,
    "completed": 8,
}

RESULT_TYPE_CODE_MAP = {
    None: 0,
    "patrol": 1,
    "tracking": 2,
    "fixed_tracking": 3,
    "underwater_search": 4,
    "preplan": 5,
}

UPDATE_TYPE_CODE_MAP = {
    "phase_only": 1,
    "result_only": 2,
    "phase_and_result": 3,
}
