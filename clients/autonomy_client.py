from config.settings import settings
from domain.models import AutonomyPatrolDispatch, AutonomyTrackingDispatch
from store.collaboration_store import collaboration_store
from utils.time_utils import utc_now
from typing import Optional
import requests


class AutonomyClient:
    def _mode(self) -> str:
        return settings.external_services.autonomy.mode.strip().lower()

    def _cfg(self):
        return settings.external_services.autonomy

    def _set_plan_url(self) -> str:
        cfg = self._cfg()
        base_url = cfg.base_url.strip()
        if base_url.rstrip("/").endswith("/api/v1/set_plan"):
            return base_url.rstrip("/")
        return base_url.rstrip("/") + "/api/v1/set_plan"

    @staticmethod
    def _payload_summary(payload_dict: dict) -> dict:
        params = payload_dict.get("params") if isinstance(payload_dict, dict) else {}
        waypoints = params.get("waypoints") if isinstance(params, dict) else None
        return {
            "task_id": payload_dict.get("task_id") if isinstance(payload_dict, dict) else None,
            "task_status": payload_dict.get("task_status") if isinstance(payload_dict, dict) else None,
            "task_mode": payload_dict.get("task_mode") if isinstance(payload_dict, dict) else None,
            "waypoint_count": len(waypoints) if isinstance(waypoints, list) else None,
            "target_id": params.get("target_id") if isinstance(params, dict) else None,
            "target_batch_no": params.get("target_batch_no") if isinstance(params, dict) else None,
        }

    @staticmethod
    def _accepted_from_response_body(body: Optional[dict], status_code: int) -> bool:
        if status_code < 200 or status_code >= 300:
            return False
        if not isinstance(body, dict):
            return True

        data = body.get("data")
        if isinstance(data, dict) and isinstance(data.get("accepted"), bool):
            return bool(data.get("accepted"))
        if isinstance(body.get("accepted"), bool):
            return bool(body.get("accepted"))

        code = body.get("code")
        if isinstance(code, int):
            return code in {0, 200}
        return True

    def _post_http_and_log(self, dispatch_kind: str, payload_dict: dict) -> dict:
        cfg = self._cfg()
        url = self._set_plan_url()
        status_code = None
        response_body = None
        error = None
        accepted = False

        try:
            response = requests.post(url, json=payload_dict, timeout=cfg.timeout_sec)
            status_code = int(response.status_code)
            try:
                response_body = response.json()
            except Exception:
                response_body = {"raw_text": response.text[:1000]}
            accepted = self._accepted_from_response_body(response_body, status_code)
        except Exception as exc:
            error = str(exc)

        collaboration_store.append_autonomy_http_dispatch_log(
            {
                "dispatch_kind": dispatch_kind,
                "mode": "http",
                "url": url,
                "timeout_sec": cfg.timeout_sec,
                "payload_summary": self._payload_summary(payload_dict),
                "status_code": status_code,
                "accepted": accepted,
                "response_body": response_body,
                "error": error,
                "dispatch_time": utc_now(),
            }
        )
        return {
            "accepted": accepted,
            "status_code": status_code,
            "response_body": response_body,
            "error": error,
            "url": url,
        }

    def post_patrol_plan(self, payload: AutonomyPatrolDispatch) -> dict:
        payload_dict = payload.model_dump(mode="json")
        if self._mode() == "http":
            return self._post_http_and_log("patrol", payload_dict)

        collaboration_store.append_autonomy_patrol_log(payload_dict)
        return {
            "code": 0,
            "message": "success",
            "data": {"accepted": True},
            "accepted": True,
        }

    def post_tracking_plan(self, payload: AutonomyTrackingDispatch) -> dict:
        payload_dict = payload.model_dump(mode="json")
        if self._mode() == "http":
            return self._post_http_and_log("tracking", payload_dict)

        collaboration_store.append_autonomy_tracking_log(payload_dict)
        return {
            "code": 0,
            "message": "success",
            "data": {"accepted": True},
            "accepted": True,
        }


autonomy_client = AutonomyClient()
