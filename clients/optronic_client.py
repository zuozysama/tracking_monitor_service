from datetime import datetime

from config.settings import settings
from domain.models import OptronicStatus
from store.collaboration_store import collaboration_store
from utils.http_client import http_get_json, http_post_json
from utils.time_utils import utc_now


class OptronicClient:
    def _mode(self) -> str:
        return settings.external_services.optronic.mode.strip().lower()

    def _cfg(self):
        return settings.external_services.optronic

    def post_power_on(self, task_id: str) -> dict:
        if self._mode() == "http":
            cfg = self._cfg()
            try:
                return http_post_json(
                    url=cfg.base_url.rstrip("/") + "/optronic/power/on",
                    timeout_sec=cfg.timeout_sec,
                    payload={"task_id": task_id},
                )
            except Exception:
                return {"accepted": False}

        status = collaboration_store.get_optronic_status(task_id)
        collaboration_store.set_optronic_status(
            task_id,
            OptronicStatus(
                is_power_on=status.is_power_on,
                last_horizontal_angle_deg=status.last_horizontal_angle_deg,
                update_time=utc_now(),
            ),
        )
        return {"accepted": True}

    def post_power_off(self, task_id: str) -> dict:
        if self._mode() == "http":
            cfg = self._cfg()
            try:
                return http_post_json(
                    url=cfg.base_url.rstrip("/") + "/optronic/power/off",
                    timeout_sec=cfg.timeout_sec,
                    payload={"task_id": task_id},
                )
            except Exception:
                return {"accepted": False}

        collaboration_store.set_optronic_status(
            task_id,
            OptronicStatus(
                is_power_on=False,
                last_horizontal_angle_deg=None,
                update_time=utc_now(),
            ),
        )
        return {"accepted": True}

    def post_initial_pointing(self, task_id: str, horizontal_angle_deg: float) -> dict:
        if self._mode() == "http":
            cfg = self._cfg()
            try:
                return http_post_json(
                    url=cfg.base_url.rstrip("/") + "/optronic/pointing/init",
                    timeout_sec=cfg.timeout_sec,
                    payload={
                        "task_id": task_id,
                        "horizontal_angle_deg": horizontal_angle_deg,
                    },
                )
            except Exception:
                return {"accepted": False}

        status = collaboration_store.get_optronic_status(task_id)
        collaboration_store.set_optronic_status(
            task_id,
            OptronicStatus(
                is_power_on=status.is_power_on,
                last_horizontal_angle_deg=horizontal_angle_deg,
                update_time=utc_now(),
            ),
        )
        return {"accepted": True}

    def get_status(self, task_id: str) -> OptronicStatus:
        if self._mode() == "http":
            cfg = self._cfg()
            try:
                resp = http_get_json(
                    url=cfg.base_url.rstrip("/") + "/optronic/status",
                    timeout_sec=cfg.timeout_sec,
                    params={"task_id": task_id},
                )
                data = resp.get("data", {})
                if "update_time" not in data or data["update_time"] is None:
                    data["update_time"] = utc_now()
                return OptronicStatus(**data)
            except Exception:
                return OptronicStatus(
                    is_power_on=False,
                    last_horizontal_angle_deg=None,
                    update_time=utc_now(),
                )

        return collaboration_store.get_optronic_status(task_id)


optronic_client = OptronicClient()