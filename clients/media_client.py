import os
import re
import subprocess
from pathlib import Path
from typing import Optional

from config.settings import settings
from store.collaboration_store import collaboration_store
from utils.http_client import http_post_json
from utils.time_utils import utc_now


class MediaClient:
    def _mode(self) -> str:
        return settings.external_services.media.mode.strip().lower()

    def _cfg(self):
        return settings.external_services.media

    @staticmethod
    def _safe_ts() -> str:
        return re.sub(r"[^0-9]", "", utc_now())[:14]

    @staticmethod
    def _build_scale_filter(target_width: Optional[int], target_height: Optional[int]) -> list[str]:
        if target_width is None or target_height is None:
            return []
        return ["-vf", f"scale={int(target_width)}:{int(target_height)}"]

    @staticmethod
    def _looks_like_webrtc_signaling_url(url: str) -> bool:
        text = (url or "").lower()
        return "index/api/webrtc" in text

    def _media_output_dir(self) -> Path:
        root = os.getenv("MEDIA_OUTPUT_DIR", "artifacts/media")
        out_dir = Path(root)
        out_dir.mkdir(parents=True, exist_ok=True)
        return out_dir

    def _task_output_dir(self, task_id: str) -> Path:
        task_dir = self._media_output_dir() / str(task_id)
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    def _resolve_stream_url(self) -> Optional[str]:
        env_url = os.getenv("MEDIA_RTSP_URL", "").strip()
        if env_url:
            return env_url
        cfg_url = (self._cfg().rtsp_url or "").strip()
        if cfg_url:
            return cfg_url
        return None

    @staticmethod
    def _run_ffmpeg(cmd: list[str], timeout_sec: int = 30) -> tuple[bool, str]:
        try:
            proc = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=timeout_sec,
                check=False,
            )
            if proc.returncode == 0:
                return True, ""
            return False, (proc.stderr or proc.stdout or "").strip()[:800]
        except Exception as exc:
            return False, str(exc)

    def capture_photo(self, task_id: str, target_width: Optional[int] = None, target_height: Optional[int] = None) -> dict:
        if self._mode() == "http":
            cfg = self._cfg()
            try:
                return http_post_json(
                    url=cfg.base_url.rstrip("/") + "/media/photo",
                    timeout_sec=cfg.timeout_sec,
                    payload={
                        "task_id": task_id,
                        "target_width": target_width,
                        "target_height": target_height,
                    },
                )
            except Exception:
                return {"success": False, "saved_local": False}

        stream_url = self._resolve_stream_url()
        if not stream_url:
            collaboration_store.append_photo_log(
                {
                    "task_id": task_id,
                    "saved_local": False,
                    "action": "photo",
                    "reason": "rtsp url not configured",
                    "time": utc_now(),
                }
            )
            return {"success": False, "saved_local": False, "reason": "stream_url_missing"}

        if self._looks_like_webrtc_signaling_url(stream_url):
            collaboration_store.append_photo_log(
                {
                    "task_id": task_id,
                    "saved_local": False,
                    "action": "photo",
                    "reason": "webrtc signaling url requires SDP exchange",
                    "stream_url": stream_url,
                    "time": utc_now(),
                }
            )
            return {"success": False, "saved_local": False, "reason": "unsupported_webrtc_signaling_url"}

        out_file = self._task_output_dir(task_id) / f"{task_id}_photo_{self._safe_ts()}.jpg"
        ffmpeg_bin = os.getenv("FFMPEG_BIN", "ffmpeg")
        cmd = [ffmpeg_bin, "-y", "-i", stream_url, *self._build_scale_filter(target_width, target_height), "-frames:v", "1", str(out_file)]
        ok, err = self._run_ffmpeg(cmd, timeout_sec=20)

        collaboration_store.append_photo_log(
            {
                "task_id": task_id,
                "saved_local": ok and out_file.exists(),
                "action": "photo",
                "file_path": str(out_file),
                "target_width": target_width,
                "target_height": target_height,
                "stream_url": stream_url,
                "error": err or None,
                "time": utc_now(),
            }
        )
        return {
            "success": ok and out_file.exists(),
            "saved_local": ok and out_file.exists(),
            "file_path": str(out_file),
            "error": err or None,
        }

    def record_video(
        self,
        task_id: str,
        duration_sec: int,
        target_width: Optional[int] = None,
        target_height: Optional[int] = None,
    ) -> dict:
        if self._mode() == "http":
            cfg = self._cfg()
            try:
                return http_post_json(
                    url=cfg.base_url.rstrip("/") + "/media/video",
                    timeout_sec=cfg.timeout_sec,
                    payload={
                        "task_id": task_id,
                        "duration_sec": duration_sec,
                        "target_width": target_width,
                        "target_height": target_height,
                    },
                )
            except Exception:
                return {"success": False, "saved_local": False}

        stream_url = self._resolve_stream_url()
        if not stream_url:
            collaboration_store.append_video_log(
                {
                    "task_id": task_id,
                    "saved_local": False,
                    "action": "video",
                    "duration_sec": duration_sec,
                    "reason": "rtsp url not configured",
                    "time": utc_now(),
                }
            )
            return {"success": False, "saved_local": False, "reason": "stream_url_missing"}

        if self._looks_like_webrtc_signaling_url(stream_url):
            collaboration_store.append_video_log(
                {
                    "task_id": task_id,
                    "saved_local": False,
                    "action": "video",
                    "duration_sec": duration_sec,
                    "reason": "webrtc signaling url requires SDP exchange",
                    "stream_url": stream_url,
                    "time": utc_now(),
                }
            )
            return {"success": False, "saved_local": False, "reason": "unsupported_webrtc_signaling_url"}

        out_file = self._task_output_dir(task_id) / f"{task_id}_video_{self._safe_ts()}.mp4"
        ffmpeg_bin = os.getenv("FFMPEG_BIN", "ffmpeg")
        cmd = [
            ffmpeg_bin,
            "-y",
            "-i",
            stream_url,
            *self._build_scale_filter(target_width, target_height),
            "-t",
            str(int(duration_sec)),
            "-c:v",
            "libx264",
            "-preset",
            "veryfast",
            "-c:a",
            "aac",
            str(out_file),
        ]
        ok, err = self._run_ffmpeg(cmd, timeout_sec=max(30, int(duration_sec) + 15))

        collaboration_store.append_video_log(
            {
                "task_id": task_id,
                "saved_local": ok and out_file.exists(),
                "action": "video",
                "duration_sec": duration_sec,
                "file_path": str(out_file),
                "target_width": target_width,
                "target_height": target_height,
                "stream_url": stream_url,
                "error": err or None,
                "time": utc_now(),
            }
        )
        return {
            "success": ok and out_file.exists(),
            "saved_local": ok and out_file.exists(),
            "file_path": str(out_file),
            "error": err or None,
        }


media_client = MediaClient()
