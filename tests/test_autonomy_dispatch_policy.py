import unittest
from datetime import timedelta
from unittest.mock import patch

from domain.enums import TaskStatus, TaskType
from domain.models import EndCondition, PatrolPlanOutput, PatrolWaypoint, TaskContext, TrackingPlanOutput
from services.collaboration_service import collaboration_service
from store.task_store import task_store
from utils.time_utils import utc_now


def _base_task(task_id: str, task_type: TaskType) -> TaskContext:
    now = utc_now()
    return TaskContext(
        task_id=task_id,
        task_type=task_type,
        end_condition=EndCondition(),
        status=TaskStatus.RUNNING,
        create_time=now,
        start_time=now,
        update_time=now,
        execution_phase="planning",
    )


class AutonomyDispatchPolicyTestCase(unittest.TestCase):
    def setUp(self) -> None:
        task_store.reset()

    def test_escort_prelock_patrol_dispatches_only_once(self):
        task = _base_task("escort-prelock-001", TaskType.ESCORT)
        task.status = TaskStatus.WAITING_TARGET
        task.patrol_plan_output = PatrolPlanOutput(
            task_id=task.task_id,
            waypoints=[
                PatrolWaypoint(longitude=121.50, latitude=31.22, expected_speed=6.0),
            ],
            update_time=utc_now(),
        )
        task_store.create_task(task)

        with patch(
            "services.collaboration_service.autonomy_client.post_patrol_plan",
            return_value={"accepted": True},
        ) as mock_post:
            collaboration_service.dispatch_autonomy_if_changed(task)

            # Force payload changes that used to trigger repeated patrol-mode dispatch.
            task.patrol_plan_output.waypoints[0].longitude = 121.55
            task.patrol_plan_output.update_time = utc_now()
            collaboration_service.dispatch_autonomy_if_changed(task)

            task.patrol_plan_output.waypoints[0].latitude = 31.25
            task.patrol_plan_output.update_time = utc_now()
            collaboration_service.dispatch_autonomy_if_changed(task)

        latest = task_store.get_task(task.task_id)
        self.assertEqual(mock_post.call_count, 1)
        self.assertTrue(latest.autonomy_patrol_dispatched_once)

    def test_underwater_search_prelock_patrol_dispatches_only_once(self):
        task = _base_task("underwater-prelock-001", TaskType.UNDERWATER_SEARCH)
        task.status = TaskStatus.WAITING_TARGET
        task.patrol_plan_output = PatrolPlanOutput(
            task_id=task.task_id,
            waypoints=[
                PatrolWaypoint(longitude=121.40, latitude=31.10, expected_speed=5.0),
            ],
            update_time=utc_now(),
        )
        task_store.create_task(task)

        with patch(
            "services.collaboration_service.autonomy_client.post_patrol_plan",
            return_value={"accepted": True},
        ) as mock_post:
            collaboration_service.dispatch_autonomy_if_changed(task)
            task.patrol_plan_output.waypoints[0].longitude = 121.45
            task.patrol_plan_output.update_time = utc_now()
            collaboration_service.dispatch_autonomy_if_changed(task)

        latest = task_store.get_task(task.task_id)
        self.assertEqual(mock_post.call_count, 1)
        self.assertTrue(latest.autonomy_patrol_dispatched_once)

    def test_autonomy_task_id_keeps_string_form(self):
        task = _base_task("00123", TaskType.PATROL)
        task.patrol_plan_output = PatrolPlanOutput(
            task_id=task.task_id,
            waypoints=[
                PatrolWaypoint(longitude=121.50, latitude=31.22, expected_speed=5.0),
            ],
            update_time=utc_now(),
        )
        task_store.create_task(task)

        with patch(
            "services.collaboration_service.autonomy_client.post_patrol_plan",
            return_value={"accepted": True},
        ) as mock_post:
            collaboration_service.dispatch_autonomy_if_changed(task)

        payload = mock_post.call_args[0][0]
        self.assertIsInstance(payload.task_id, str)
        self.assertEqual(payload.task_id, "00123")

    def test_autonomy_dispatch_failure_uses_backoff_retry(self):
        task = _base_task("escort-track-001", TaskType.ESCORT)
        task.tracking_plan_output = TrackingPlanOutput(
            task_id=task.task_id,
            target_id="target-1",
            target_batch_no=1,
            rel_range_m=800.0,
            relative_bearing_deg=35.0,
            expected_speed=6.0,
            update_time=utc_now(),
        )
        task_store.create_task(task)

        with patch(
            "services.collaboration_service.autonomy_client.post_tracking_plan",
            return_value={"accepted": False},
        ) as mock_post:
            collaboration_service.dispatch_autonomy_if_changed(task)
            self.assertEqual(mock_post.call_count, 1)

            first_retry_deadline = task.autonomy_retry_next_time
            self.assertIsNotNone(first_retry_deadline)
            self.assertEqual(task.autonomy_retry_attempts, 1)

            # Immediate retry should be throttled by backoff window.
            collaboration_service.dispatch_autonomy_if_changed(task)
            self.assertEqual(mock_post.call_count, 1)

            # Advance retry window and verify next retry can happen.
            task.autonomy_retry_next_time = utc_now() - timedelta(seconds=1)
            task_store.update_task(task)
            collaboration_service.dispatch_autonomy_if_changed(task)
            self.assertEqual(mock_post.call_count, 2)
            self.assertEqual(task.autonomy_retry_attempts, 2)
            self.assertEqual(
                (task.autonomy_retry_next_time - utc_now()) > timedelta(seconds=0),
                True,
            )

            # Keep failing until max attempts reached; then no more retries should be sent.
            for _ in range(3):
                task.autonomy_retry_next_time = utc_now() - timedelta(seconds=1)
                task_store.update_task(task)
                collaboration_service.dispatch_autonomy_if_changed(task)
            self.assertEqual(mock_post.call_count, 5)
            self.assertEqual(task.autonomy_retry_attempts, 5)

            task.autonomy_retry_next_time = utc_now() - timedelta(seconds=1)
            task_store.update_task(task)
            collaboration_service.dispatch_autonomy_if_changed(task)
            self.assertEqual(mock_post.call_count, 5)


if __name__ == "__main__":
    unittest.main()
