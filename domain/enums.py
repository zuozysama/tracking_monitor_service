from enum import Enum


class TaskType(str, Enum):
    PATROL = "patrol"
    ESCORT = "escort"
    INTERCEPT = "intercept"
    EXPEL = "expel"
    UNDERWATER_SEARCH = "underwater_search"
    FIXED_TRACKING = "fixed_tracking"
    PREPLAN = "preplan"


class TrackingMode(str, Enum):
    ESCORT = "escort"
    INTERCEPT = "intercept"
    EXPEL = "expel"


class TaskStatus(str, Enum):
    CREATED = "created"
    RUNNING = "running"
    WAITING_TARGET = "waiting_target"
    COMPLETED = "completed"
    TERMINATED = "terminated"
    ABNORMAL = "abnormal"


class FinishReason(str, Enum):
    MANUAL_TERMINATED = "manual_terminated"
    TIMEOUT = "timeout"
    TARGET_LOST = "target_lost"
    COMPLETED = "completed"
    OUT_OF_REGION = "out_of_region"
    SONAR_UNMATCHED = "sonar_unmatched"
    DATA_TIMEOUT = "data_timeout"
    INVALID_TASK = "invalid_task"
    SYSTEM_ERROR = "system_error"
