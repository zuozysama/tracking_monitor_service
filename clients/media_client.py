import os
import re
import subprocess
import tempfile
import time
from threading import Event
from uuid import uuid4

from clients.media_routing import FRONT_CHANNEL, REAR_CHANNEL
from pathlib import Path
from typing import Optional

from config.settings import settings
from config.media_sources import gd_stream_sources, media_output_dir
from utils.url_utils import redact_url_credentials, redact_stream_text
from store.collaboration_store import collaboration_store
from utils.http_client import http_post_json
from utils.time_utils import utc_now


class MediaClient:
    @staticmethod
    def _tail_text(text: str, max_chars: int = 2000) -> str:
        if len(text) <= max_chars:
            return text
        return f"...(truncated, showing last {max_chars} chars)\n{text[-max_chars:]}"

    def _mode(self) -> str:
        return settings.external_services.media.mode.strip().lower()

    def _cfg(self):
        return settings.external_services.media

    @staticmethod
    def _safe_ts() -> str:
        return re.sub(r"[^0-9]", "", utc_now().isoformat())[:14]

    @staticmethod
    def _build_scale_filter(target_width: Optional[int], target_height: Optional[int]) -> list[str]:
        if target_width is None or target_height is None:
            return []
        return ["-vf", f"scale={int(target_width)}:{int(target_height)}"]

    @staticmethod
    def _get_env_positive_int(name: str) -> Optional[int]:
        raw = (os.getenv(name, "") or "").strip()
        if not raw:
            return None
        try:
            value = int(raw)
        except Exception:
            return None
        if value <= 0:
            return None
        return value

    @staticmethod
    def _get_env_bool(name: str, default: bool) -> bool:
        raw = (os.getenv(name, "") or "").strip().lower()
        if not raw:
            return default
        if raw in {"1", "true", "yes", "y", "on"}:
            return True
        if raw in {"0", "false", "no", "n", "off"}:
            return False
        return default

    @staticmethod
    def _looks_like_webrtc_signaling_url(url: str) -> bool:
        text = (url or "").lower()
        return "index/api/webrtc" in text

    def _media_output_dir(self) -> Path:
        return media_output_dir()

    def _task_output_dir(self, task_id: str) -> Path:
        root = self._media_output_dir().resolve()
        task_dir = (root / str(task_id)).resolve()
        if not str(task_id).strip() or task_dir.parent != root:
            raise ValueError("task_id must identify a single directory inside MEDIA_OUTPUT_DIR")
        task_dir.mkdir(parents=True, exist_ok=True)
        return task_dir

    def dual_stream_enabled(self) -> bool:
        # Existing HTTP media endpoints retain their original contract.
        # Tracking always selects a side. A missing side must never silently
        # fall back to the legacy single-source URL.
        return self._mode() != "http"

    def _channel_url(self, channel_id: str) -> str:
        side = {FRONT_CHANNEL: "front", REAR_CHANNEL: "rear"}.get(channel_id)
        if side is None:
            return ""
        return gd_stream_sources().get(side, "")

    def _resolve_stream_url(self, channel_id: Optional[str] = None) -> Optional[str]:
        if channel_id is not None:
            return self._channel_url(channel_id) or None
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
            stderr_text = (proc.stderr or "").strip()
            stdout_text = (proc.stdout or "").strip()
            detail = stderr_text or stdout_text or "ffmpeg exited with non-zero code and no output"
            return False, redact_stream_text(f"ffmpeg exit_code={proc.returncode}; detail={MediaClient._tail_text(detail)}")
        except Exception as exc:
            return False, redact_stream_text(exc)

    @staticmethod
    def _run_segment(cmd: list[str], stop_event: Event, timeout_sec: int) -> tuple[bool, str]:
        if stop_event.is_set():
            return False, "recording_cancelled_before_start"
        process = None
        try:
            with tempfile.TemporaryFile() as error_log:
                process = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=error_log)
                deadline = time.monotonic() + timeout_sec
                timed_out = False
                while process.poll() is None:
                    if stop_event.wait(0.1) or time.monotonic() >= deadline:
                        timed_out = time.monotonic() >= deadline
                        try:
                            process.stdin.write(b"q\n")
                            process.stdin.flush()
                        except (BrokenPipeError, OSError):
                            pass
                        try:
                            process.wait(timeout=4)
                        except subprocess.TimeoutExpired:
                            process.terminate()
                            try:
                                process.wait(timeout=2)
                            except subprocess.TimeoutExpired:
                                process.kill()
                                process.wait(timeout=2)
                        break
                if timed_out:
                    return False, "recording_timeout"
                if process.returncode == 0:
                    return True, ""
                # Raw FFmpeg output can include source credentials.
                return False, f"ffmpeg exit_code={process.returncode}"
        except Exception as exc:
            return False, f"recording_error:{type(exc).__name__}"
        finally:
            if process is not None:
                if process.poll() is None:
                    process.kill()
                    process.wait(timeout=2)
                if process.stdin is not None:
                    process.stdin.close()

    def capture_photo(self, task_id: str, target_width: Optional[int] = None, target_height: Optional[int] = None, *, channel_id: Optional[str] = None) -> dict:
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

        try:
            stream_url = self._resolve_stream_url(channel_id) if channel_id else self._resolve_stream_url()
        except ValueError as exc:
            return {"success": False, "saved_local": False, "reason": "source_configuration_error", "error": str(exc), "channel_id": channel_id or ""}
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
            return {"success": False, "saved_local": False, "reason": "stream_url_missing", "channel_id": channel_id or ""}

        if self._looks_like_webrtc_signaling_url(stream_url):
            collaboration_store.append_photo_log(
                {
                    "task_id": task_id,
                    "saved_local": False,
                    "action": "photo",
                    "reason": "webrtc signaling url requires SDP exchange",
                    "stream_url": redact_url_credentials(stream_url),
                    "time": utc_now(),
                }
            )
            return {"success": False, "saved_local": False, "reason": "unsupported_webrtc_signaling_url", "channel_id": channel_id or ""}

        suffix = f"_{channel_id}_{uuid4().hex[:8]}" if channel_id else ""
        try:
            out_file = self._task_output_dir(task_id) / f"{task_id}_photo_{self._safe_ts()}{suffix}.jpg"
        except (OSError, ValueError):
            return {"success": False, "saved_local": False, "reason": "storage_unavailable", "channel_id": channel_id or ""}
        ffmpeg_bin = os.getenv("FFMPEG_BIN", "ffmpeg")
        cmd = [ffmpeg_bin, "-y", *self._stream_input_args(stream_url), "-i", stream_url, *self._build_scale_filter(target_width, target_height), "-frames:v", "1", str(out_file)]
        ok, err = self._run_ffmpeg(cmd, timeout_sec=20)
        err = redact_stream_text(err)

        collaboration_store.append_photo_log(
            {
                "task_id": task_id,
                "saved_local": ok and out_file.exists(),
                "action": "photo",
                "file_path": str(out_file),
                "target_width": target_width,
                "target_height": target_height,
                "stream_url": redact_url_credentials(stream_url),
                "error": err or None,
                "time": utc_now(),
            }
        )
        return {
            "success": ok and out_file.exists(),
            "saved_local": ok and out_file.exists(),
            "file_path": str(out_file),
            "channel_id": channel_id or "",
            "error": err or None,
        }

    def record_video(
        self,
        task_id: str,
        duration_sec: int,
        target_width: Optional[int] = None,
        target_height: Optional[int] = None,
        *,
        channel_id: Optional[str] = None,
        stop_event: Optional[Event] = None,
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

        try:
            stream_url = self._resolve_stream_url(channel_id) if channel_id else self._resolve_stream_url()
        except ValueError as exc:
            return {"success": False, "saved_local": False, "reason": "source_configuration_error", "error": str(exc), "channel_id": channel_id or ""}
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
            return {"success": False, "saved_local": False, "reason": "stream_url_missing", "channel_id": channel_id or ""}

        if self._looks_like_webrtc_signaling_url(stream_url):
            collaboration_store.append_video_log(
                {
                    "task_id": task_id,
                    "saved_local": False,
                    "action": "video",
                    "duration_sec": duration_sec,
                    "reason": "webrtc signaling url requires SDP exchange",
                    "stream_url": redact_url_credentials(stream_url),
                    "time": utc_now(),
                }
            )
            return {"success": False, "saved_local": False, "reason": "unsupported_webrtc_signaling_url", "channel_id": channel_id or ""}

        resolved_target_width = target_width
        resolved_target_height = target_height
        if resolved_target_width is None:
            resolved_target_width = self._get_env_positive_int("MEDIA_VIDEO_TARGET_WIDTH")
        if resolved_target_height is None:
            resolved_target_height = self._get_env_positive_int("MEDIA_VIDEO_TARGET_HEIGHT")
        keep_audio = self._get_env_bool("MEDIA_VIDEO_KEEP_AUDIO", default=True)
        preset = (os.getenv("MEDIA_VIDEO_PRESET", "ultrafast") or "").strip() or "ultrafast"

        suffix = f"_{channel_id}_{uuid4().hex[:8]}" if channel_id else ""
        try:
            out_file = self._task_output_dir(task_id) / f"{task_id}_video_{self._safe_ts()}{suffix}.mp4"
        except (OSError, ValueError):
            return {"success": False, "saved_local": False, "reason": "storage_unavailable", "channel_id": channel_id or ""}
        ffmpeg_bin = os.getenv("FFMPEG_BIN", "ffmpeg")
        cmd = [
            ffmpeg_bin,
            "-y",
            *self._stream_input_args(stream_url),
            "-i",
            stream_url,
            *self._build_scale_filter(resolved_target_width, resolved_target_height),
            "-t",
            str(int(duration_sec)),
            "-c:v",
            "libx264",
            "-preset",
            preset,
        ]
        if keep_audio:
            cmd.extend(["-c:a", "aac"])
        else:
            cmd.append("-an")
        cmd.append(str(out_file))
        if stop_event is None:
            ok, err = self._run_ffmpeg(cmd, timeout_sec=max(30, int(duration_sec) + 15))
        else:
            ok, err = self._run_segment(cmd, stop_event, max(30, int(duration_sec) + 15))
        err = redact_stream_text(err)

        collaboration_store.append_video_log(
            {
                "task_id": task_id,
                "saved_local": ok and out_file.exists(),
                "action": "video",
                "duration_sec": duration_sec,
                "file_path": str(out_file),
                "target_width": resolved_target_width,
                "target_height": resolved_target_height,
                "keep_audio": keep_audio,
                "video_preset": preset,
                "stream_url": redact_url_credentials(stream_url),
                "error": err or None,
                "time": utc_now(),
            }
        )
        return {
            "success": ok and out_file.exists(),
            "saved_local": ok and out_file.exists(),
            "file_path": str(out_file),
            "channel_id": channel_id or "",
            "error": err or None,
        }


    @staticmethod
    def _stream_input_args(stream_url):
        if str(stream_url).lower().startswith(("rtsp://", "rtsps://")):
            return ["-rtsp_transport", "tcp", "-timeout", "5000000"]
        return []


media_client = MediaClient()
