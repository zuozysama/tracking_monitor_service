from datetime import datetime
from typing import Dict, List, Optional

from domain.models import OpticalLinkageCommand, OptronicStatus, SonarMatchStatus


class CollaborationStore:
    def __init__(self) -> None:
        self._optronic_status_by_task: Dict[str, OptronicStatus] = {}
        self._photo_logs: List[dict] = []
        self._video_logs: List[dict] = []
        self._media_stream_access_logs: List[dict] = []
        self._planning_stage_logs: List[dict] = []
        self._planning_plan_logs: List[dict] = []
        self._sonar_status_by_task: Dict[str, SonarMatchStatus] = {}
        self._autonomy_patrol_logs: List[dict] = []
        self._autonomy_tracking_logs: List[dict] = []
        self._optical_linkage_logs: List[dict] = []
        self._manual_selection_requests: List[dict] = []
        self._manual_switch_requests: List[dict] = []
        self._manual_selection_feedbacks: List[dict] = []
        self._manual_switch_feedbacks: List[dict] = []
        self._dds_publish_logs: List[dict] = []

    def get_optronic_status(self, task_id: str) -> OptronicStatus:
        if task_id not in self._optronic_status_by_task:
            self._optronic_status_by_task[task_id] = OptronicStatus(
                is_power_on=False,
                last_horizontal_angle_deg=None,
                update_time=datetime.utcnow(),
            )
        return self._optronic_status_by_task[task_id]

    def set_optronic_status(self, task_id: str, status: OptronicStatus) -> None:
        self._optronic_status_by_task[task_id] = status

    def append_photo_log(self, item: dict) -> None:
        self._photo_logs.append(item)

    def append_video_log(self, item: dict) -> None:
        self._video_logs.append(item)

    def append_media_stream_access_log(self, item: dict) -> None:
        self._media_stream_access_logs.append(item)

    def append_stage_log(self, item: dict) -> None:
        self._planning_stage_logs.append(item)

    def append_plan_log(self, item: dict) -> None:
        self._planning_plan_logs.append(item)

    def get_photo_logs(self) -> List[dict]:
        return self._photo_logs

    def get_video_logs(self) -> List[dict]:
        return self._video_logs

    def get_media_stream_access_logs(self) -> List[dict]:
        return self._media_stream_access_logs

    def get_latest_stream_access_by_task(self, task_id: str) -> Optional[dict]:
        for item in reversed(self._media_stream_access_logs):
            request = item.get("request") or {}
            if request.get("task_id") == task_id:
                return item
        return None

    def get_stage_logs(self) -> List[dict]:
        return self._planning_stage_logs

    def get_plan_logs(self) -> List[dict]:
        return self._planning_plan_logs

    def get_sonar_status(self, task_id: str) -> SonarMatchStatus:
        if task_id not in self._sonar_status_by_task:
            self._sonar_status_by_task[task_id] = SonarMatchStatus(
                matched=True,
                confidence=1.0,
                update_time=datetime.utcnow(),
            )
        return self._sonar_status_by_task[task_id]

    def set_sonar_status(self, task_id: str, status: SonarMatchStatus) -> None:
        self._sonar_status_by_task[task_id] = status

    def append_autonomy_patrol_log(self, item: dict) -> None:
        self._autonomy_patrol_logs.append(item)

    def append_autonomy_tracking_log(self, item: dict) -> None:
        self._autonomy_tracking_logs.append(item)

    def get_autonomy_patrol_logs(self) -> List[dict]:
        return self._autonomy_patrol_logs

    def get_autonomy_tracking_logs(self) -> List[dict]:
        return self._autonomy_tracking_logs

    def append_optical_linkage_log(self, item: dict) -> None:
        self._optical_linkage_logs.append(item)

    def get_optical_linkage_logs(self) -> List[dict]:
        return self._optical_linkage_logs

    def append_manual_selection_request(self, item: dict) -> None:
        self._manual_selection_requests.append(item)

    def append_manual_switch_request(self, item: dict) -> None:
        self._manual_switch_requests.append(item)

    def append_manual_selection_feedback(self, item: dict) -> None:
        self._manual_selection_feedbacks.append(item)

    def append_manual_switch_feedback(self, item: dict) -> None:
        self._manual_switch_feedbacks.append(item)

    def get_manual_selection_requests(self) -> List[dict]:
        return self._manual_selection_requests

    def get_manual_switch_requests(self) -> List[dict]:
        return self._manual_switch_requests

    def get_manual_selection_feedbacks(self) -> List[dict]:
        return self._manual_selection_feedbacks

    def get_manual_switch_feedbacks(self) -> List[dict]:
        return self._manual_switch_feedbacks

    def append_dds_publish_log(self, item: dict) -> None:
        self._dds_publish_logs.append(item)

    def get_dds_publish_logs(self) -> List[dict]:
        return self._dds_publish_logs

    def reset(self) -> None:
        self._optronic_status_by_task.clear()
        self._photo_logs.clear()
        self._video_logs.clear()
        self._media_stream_access_logs.clear()
        self._planning_stage_logs.clear()
        self._planning_plan_logs.clear()
        self._sonar_status_by_task.clear()
        self._autonomy_patrol_logs.clear()
        self._autonomy_tracking_logs.clear()
        self._optical_linkage_logs.clear()
        self._manual_selection_requests.clear()
        self._manual_switch_requests.clear()
        self._manual_selection_feedbacks.clear()
        self._manual_switch_feedbacks.clear()
        self._dds_publish_logs.clear()


collaboration_store = CollaborationStore()
