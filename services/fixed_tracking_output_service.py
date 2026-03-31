from domain.enums import TaskStatus
from domain.models import TaskContext, FixedTrackingOutput
from store.task_store import task_store
from utils.time_utils import utc_now


class FixedTrackingOutputService:
    def refresh_output(self, task: TaskContext) -> None:
        if task.status not in {TaskStatus.RUNNING, TaskStatus.WAITING_TARGET}:
            return

        if task.recommended_point is None:
            task.fixed_tracking_output = None
            task.update_time = utc_now()
            task_store.update_task(task)
            return

        task.fixed_tracking_output = FixedTrackingOutput(
            task_id=task.task_id,
            anchor_longitude=task.recommended_point.longitude,
            anchor_latitude=task.recommended_point.latitude,
            expected_speed=task.expected_speed,
            update_time=utc_now(),
        )
        task.update_time = utc_now()
        task_store.update_task(task)


fixed_tracking_output_service = FixedTrackingOutputService()
