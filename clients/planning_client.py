from config.settings import settings
from store.collaboration_store import collaboration_store
from utils.http_client import http_post_json
from utils.time_utils import utc_now


class PlanningClient:
    def _mode(self) -> str:
        return settings.external_services.planning.mode.strip().lower()

    def _cfg(self):
        return settings.external_services.planning

    def report_stage(self, task_id: str, stage: str) -> dict:
        if self._mode() == "http":
            cfg = self._cfg()
            try:
                return http_post_json(
                    url=cfg.base_url.rstrip("/") + "/planning/report/stage",
                    timeout_sec=cfg.timeout_sec,
                    payload={
                        "task_id": task_id,
                        "stage": stage,
                    },
                )
            except Exception:
                return {"accepted": False}

        collaboration_store.append_stage_log(
            {
                "task_id": task_id,
                "stage": stage,
                "report_time": utc_now(),
            }
        )
        return {"accepted": True}

    def report_plan(self, task_id: str, plan_type: str, plan_payload: dict) -> dict:
        if self._mode() == "http":
            cfg = self._cfg()
            try:
                return http_post_json(
                    url=cfg.base_url.rstrip("/") + "/planning/report/plan",
                    timeout_sec=cfg.timeout_sec,
                    payload={
                        "task_id": task_id,
                        "plan_type": plan_type,
                        "plan_payload": plan_payload,
                    },
                )
            except Exception:
                return {"accepted": False}

        collaboration_store.append_plan_log(
            {
                "task_id": task_id,
                "plan_type": plan_type,
                "plan_payload": plan_payload,
                "report_time": utc_now(),
            }
        )
        return {"accepted": True}


planning_client = PlanningClient()