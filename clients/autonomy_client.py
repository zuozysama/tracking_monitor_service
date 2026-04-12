from config.settings import settings
from domain.models import AutonomyPatrolDispatch, AutonomyTrackingDispatch
from store.collaboration_store import collaboration_store
from utils.http_client import http_post_json


class AutonomyClient:
    def _mode(self) -> str:
        return settings.external_services.autonomy.mode.strip().lower()

    def _cfg(self):
        return settings.external_services.autonomy

    def post_patrol_plan(self, payload: AutonomyPatrolDispatch) -> dict:
        if self._mode() == "http":
            cfg = self._cfg()
            try:
                return http_post_json(
                    url=cfg.base_url.rstrip("/") + "/api/v1/internal/patrol/dispatch",
                    timeout_sec=cfg.timeout_sec,
                    payload=payload.model_dump(mode="json"),
                )
            except Exception:
                return {
                    "code": -1,
                    "message": "http patrol dispatch failed",
                    "data": {"accepted": False},
                }

        collaboration_store.append_autonomy_patrol_log(payload.model_dump(mode="json"))
        return {
            "code": 0,
            "message": "success",
            "data": {"accepted": True},
        }

    def post_tracking_plan(self, payload: AutonomyTrackingDispatch) -> dict:
        if self._mode() == "http":
            cfg = self._cfg()
            try:
                return http_post_json(
                    url=cfg.base_url.rstrip("/") + "/api/v1/internal/tracking/dispatch",
                    timeout_sec=cfg.timeout_sec,
                    payload=payload.model_dump(mode="json"),
                )
            except Exception:
                return {
                    "code": -1,
                    "message": "http tracking dispatch failed",
                    "data": {"accepted": False},
                }

        collaboration_store.append_autonomy_tracking_log(payload.model_dump(mode="json"))
        return {
            "code": 0,
            "message": "success",
            "data": {"accepted": True},
        }


autonomy_client = AutonomyClient()
