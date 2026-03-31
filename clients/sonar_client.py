from config.settings import settings
from domain.models import SonarMatchStatus
from store.collaboration_store import collaboration_store
from utils.http_client import http_get_json
from utils.time_utils import utc_now


class SonarClient:
    def _mode(self) -> str:
        return settings.external_services.sonar.mode.strip().lower()

    def _cfg(self):
        return settings.external_services.sonar

    def get_match_status(self, task_id: str) -> SonarMatchStatus:
        if self._mode() == "http":
            cfg = self._cfg()
            try:
                resp = http_get_json(
                    url=cfg.base_url.rstrip("/") + "/sonar/match/status",
                    timeout_sec=cfg.timeout_sec,
                    params={"task_id": task_id},
                )
                data = resp.get("data", {})
                if "update_time" not in data or data["update_time"] is None:
                    data["update_time"] = utc_now()
                return SonarMatchStatus(**data)
            except Exception:
                return SonarMatchStatus(
                    matched=True,
                    confidence=1.0,
                    update_time=utc_now(),
                )

        return collaboration_store.get_sonar_status(task_id)


sonar_client = SonarClient()