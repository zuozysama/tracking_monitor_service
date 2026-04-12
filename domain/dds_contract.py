from domain.enums import FinishReason, TaskStatus, TaskType

TASK_UPDATE_TOPIC = "task_update_topic"
PREPLAN_RESULT_TOPIC = "preplan_result_topic"
MANUAL_SELECTION_REQUEST_TOPIC = "manual_selection_request_topic"
MANUAL_SWITCH_REQUEST_TOPIC = "manual_switch_request_topic"
ELECTRO_OPTICAL_LINKAGE_CMD_TOPIC = "electro_optical_linkage_cmd_topic"
STREAM_MEDIA_PARAM_TOPIC = "stream_media_param_topic"
OWNSHIP_NAVIGATION_TOPIC = "ownship_navigation_topic"
TARGET_PERCEPTION_TOPIC = "target_perception_topic"

TASK_TYPE_CODE_MAP = {
    TaskType.PATROL: 1,
    TaskType.TRACKING: 2,
    TaskType.FIXED_TRACKING: 3,
    TaskType.UNDERWATER_SEARCH: 4,
    TaskType.PREPLAN: 5,
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
