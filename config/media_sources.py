"""Shared environment/YAML configuration for media inputs and local storage."""
import os
from pathlib import Path
import tempfile
from urllib.parse import urlsplit

PROJECT_ROOT = Path(__file__).resolve().parents[1]
MEDIA_ENV_NAMES = ("MEDIA_FRONT_RTSP_URL", "MEDIA_REAR_RTSP_URL", "MEDIA_OUTPUT_DIR")


def validate_rtsp_url(value, name="视频地址", required=False):
    value = str(value or "").strip()
    try:
        valid = not value and not required
        if value:
            parsed = urlsplit(value)
            valid = parsed.scheme in {"rtsp", "rtsps"} and bool(parsed.hostname)
            parsed.port
    except ValueError:
        valid = False
    if not valid:
        raise ValueError(f"{name}：请配置完整有效的 rtsp:// 或 rtsps:// 地址。")
    return value


def _configured(name, field, fallback=""):
    from config.settings import settings
    return (os.getenv(name, "") or "").strip() or str(
        getattr(settings.external_services.media, field, fallback) or fallback
    ).strip()


def gd_stream_sources(*, validate=True):
    sources = {"front": _configured("MEDIA_FRONT_RTSP_URL", "front_rtsp_url"),
               "rear": _configured("MEDIA_REAR_RTSP_URL", "rear_rtsp_url")}
    if validate:
        for side, name in (("front", "MEDIA_FRONT_RTSP_URL"), ("rear", "MEDIA_REAR_RTSP_URL")):
            sources[side] = validate_rtsp_url(sources[side], name)
    return sources


def media_output_dir(value=None, *, check_writable=False):
    raw = str(value or "").strip() if value is not None else _configured("MEDIA_OUTPUT_DIR", "output_dir", "artifacts/media")
    raw = raw or "artifacts/media"
    try:
        path = Path(raw).expanduser()
        if not path.is_absolute():
            path = PROJECT_ROOT / path
        path = path.resolve()
        path.mkdir(parents=True, exist_ok=True)
        if check_writable:
            with tempfile.TemporaryFile(dir=path, prefix=".media-write-check-") as probe:
                probe.write(b"ok")
                probe.flush()
    except (OSError, ValueError):
        raise ValueError("MEDIA_OUTPUT_DIR：无法创建或写入存储目录，请检查路径和权限。") from None
    return path
