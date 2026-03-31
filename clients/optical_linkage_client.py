from config.settings import settings
from domain.models import OpticalLinkageCommand
from store.collaboration_store import collaboration_store
from utils.http_client import http_post_json
from utils.time_utils import utc_now


class OpticalLinkageClient:
    def _mode(self) -> str:
        return settings.external_services.optronic.mode.strip().lower()

    def _cfg(self):
        return settings.external_services.optronic

    def post_command(self, task_id: str, payload: OpticalLinkageCommand) -> dict:
        if self._mode() == "http":
            cfg = self._cfg()
            try:
                return http_post_json(
                    url=cfg.base_url.rstrip("/") + "/optical-linkage/dispatch",
                    timeout_sec=cfg.timeout_sec,
                    payload=payload.model_dump(mode="json"),
                )
            except Exception:
                return {"accepted": False}

        collaboration_store.append_optical_linkage_log(
            {
                "task_id": task_id,
                "payload": payload.model_dump(mode="json"),
                "dispatch_time": utc_now(),
            }
        )
        return {"accepted": True}


optical_linkage_client = OpticalLinkageClient()
