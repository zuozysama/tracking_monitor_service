from config.settings import settings
from domain.models import MediaStreamAccessRequest
from store.collaboration_store import collaboration_store
from utils.http_client import http_post_json
from utils.time_utils import utc_now


class MediaClient:
    def _mode(self) -> str:
        return settings.external_services.media.mode.strip().lower()

    def _cfg(self):
        return settings.external_services.media

    def get_stream_access(self, req: MediaStreamAccessRequest) -> dict:
        if self._mode() == "http":
            cfg = self._cfg()
            try:
                return http_post_json(
                    url=cfg.base_url.rstrip("/") + "/media/stream/access",
                    timeout_sec=cfg.timeout_sec,
                    payload=req.model_dump(mode="json"),
                )
            except Exception:
                return {
                    "code": -1,
                    "message": "http media stream access failed",
                    "data": {"accepted": False},
                }

        data = {
            "stream_id": f"stream-{req.task_id}",
            "media_protocol": req.media_protocol,
            "access_url": f"https://mock.media.local/{req.channel_id}/{req.task_id}",
            "session_token": f"token-{req.task_id}",
            "expires_in_sec": 60,
        }
        collaboration_store.append_media_stream_access_log(
            {
                "request": req.model_dump(mode="json"),
                "response": data,
                "time": utc_now(),
            }
        )
        return {
            "code": 0,
            "message": "success",
            "data": data,
        }

    def capture_photo(self, task_id: str) -> dict:
        if self._mode() == "http":
            cfg = self._cfg()
            try:
                return http_post_json(
                    url=cfg.base_url.rstrip("/") + "/media/photo",
                    timeout_sec=cfg.timeout_sec,
                    payload={"task_id": task_id},
                )
            except Exception:
                return {"success": False, "saved_local": False}

        collaboration_store.append_photo_log(
            {
                "task_id": task_id,
                "saved_local": True,
                "action": "photo",
                "time": utc_now(),
            }
        )
        return {"success": True, "saved_local": True}

    def record_video(self, task_id: str, duration_sec: int) -> dict:
        if self._mode() == "http":
            cfg = self._cfg()
            try:
                return http_post_json(
                    url=cfg.base_url.rstrip("/") + "/media/video",
                    timeout_sec=cfg.timeout_sec,
                    payload={
                        "task_id": task_id,
                        "duration_sec": duration_sec,
                    },
                )
            except Exception:
                return {"success": False, "saved_local": False}

        collaboration_store.append_video_log(
            {
                "task_id": task_id,
                "saved_local": True,
                "action": "video",
                "duration_sec": duration_sec,
                "time": utc_now(),
            }
        )
        return {"success": True, "saved_local": True}


media_client = MediaClient()
