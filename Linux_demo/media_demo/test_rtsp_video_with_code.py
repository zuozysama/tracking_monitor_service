#!/usr/bin/env python3
"""
Probe one or more RTSP URLs through the current MediaClient video pipeline.

This script does NOT inject navigation/perception and does NOT call task APIs.
It directly exercises clients.media_client.MediaClient.record_video(...) so you
can quickly verify whether current code can process a candidate stream.
"""

'''
python Linux_demo/media_demo/test_rtsp_video_with_code.py \
  --output-dir /app/media \
  --duration-sec 4 \
  --rtsp-url "rtsp://admin:1qaz2wsx,.@172.16.10.114:544/Streaming/Chanals/101"
'''


from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime
from pathlib import Path
from typing import Any


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_urls(args: argparse.Namespace) -> list[str]:
    urls: list[str] = []
    for item in args.rtsp_url:
        value = (item or "").strip()
        if value:
            urls.append(value)

    if args.rtsp_file:
        file_path = Path(args.rtsp_file)
        if not file_path.is_file():
            raise FileNotFoundError(f"rtsp file not found: {file_path}")
        for raw in file_path.read_text(encoding="utf-8").splitlines():
            line = raw.strip()
            if not line or line.startswith("#"):
                continue
            urls.append(line)

    # Keep order, remove duplicates.
    dedup: list[str] = []
    seen: set[str] = set()
    for url in urls:
        if url in seen:
            continue
        seen.add(url)
        dedup.append(url)
    return dedup


def _tail_task_video_log(collaboration_store: Any, task_id: str) -> dict[str, Any] | None:
    items = collaboration_store.get_video_logs()
    for item in reversed(items):
        if item.get("task_id") == task_id:
            return item
    return None


def _probe_one(
    *,
    media_client: Any,
    collaboration_store: Any,
    url: str,
    idx: int,
    duration_sec: int,
    output_dir: str,
    task_prefix: str,
) -> dict[str, Any]:
    now = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    task_id = f"{task_prefix}-{idx:02d}-{now}"

    os.environ["MEDIA_RTSP_URL"] = url

    started = time.time()
    result = media_client.record_video(task_id=task_id, duration_sec=duration_sec)
    elapsed_sec = round(time.time() - started, 3)

    file_path = str(result.get("file_path") or "")
    file_exists = bool(file_path) and Path(file_path).is_file()
    file_size = Path(file_path).stat().st_size if file_exists else 0

    expected_prefix = str(Path(output_dir) / task_id)
    path_prefix_ok = file_path.startswith(expected_prefix) if file_path else False
    tail_log = _tail_task_video_log(collaboration_store, task_id)

    return {
        "task_id": task_id,
        "rtsp_url": url,
        "elapsed_sec": elapsed_sec,
        "record_video_result": result,
        "file_exists": file_exists,
        "file_size_bytes": file_size,
        "expected_prefix": expected_prefix,
        "path_prefix_ok": path_prefix_ok,
        "tail_video_log": tail_log,
    }


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Test current MediaClient video processing with one or more RTSP URLs.",
    )
    parser.add_argument(
        "--rtsp-url",
        action="append",
        default=[],
        help="RTSP URL to test (can be repeated).",
    )
    parser.add_argument(
        "--rtsp-file",
        default="",
        help="Path to a text file containing RTSP URLs (one per line).",
    )
    parser.add_argument(
        "--duration-sec",
        type=int,
        default=4,
        help="Record duration per URL in seconds.",
    )
    parser.add_argument(
        "--output-dir",
        default="/app/media",
        help="MEDIA_OUTPUT_DIR to use for this probe process.",
    )
    parser.add_argument(
        "--task-prefix",
        default="task-video-probe",
        help="Task id prefix for output file naming.",
    )
    parser.add_argument(
        "--continue-on-fail",
        action="store_true",
        help="Keep probing remaining URLs even if one fails.",
    )
    args = parser.parse_args()

    urls = _load_urls(args)
    if not urls:
        print("[error] no RTSP URL provided. Use --rtsp-url or --rtsp-file.", file=sys.stderr)
        return 2

    # Ensure imports resolve from repo root.
    repo_root = _repo_root()
    sys.path.insert(0, str(repo_root))
    os.chdir(repo_root)

    # Force local media processing path in this subprocess.
    os.environ["EXTERNAL_MEDIA_MODE"] = "mock"
    os.environ["MEDIA_OUTPUT_DIR"] = args.output_dir

    from clients.media_client import media_client  # noqa: WPS433
    from config.settings import settings  # noqa: WPS433
    from store.collaboration_store import collaboration_store  # noqa: WPS433

    print("=== RTSP Video Probe (current code path) ===")
    print(f"[info] cwd={repo_root}")
    print(f"[info] media_mode={settings.external_services.media.mode}")
    print(f"[info] media_output_dir={os.environ.get('MEDIA_OUTPUT_DIR')}")
    print(f"[info] test_count={len(urls)} duration_sec={args.duration_sec}")
    print()

    any_fail = False
    for idx, url in enumerate(urls, 1):
        print(f"--- [{idx}/{len(urls)}] probing url ---")
        print(url)
        probe = _probe_one(
            media_client=media_client,
            collaboration_store=collaboration_store,
            url=url,
            idx=idx,
            duration_sec=args.duration_sec,
            output_dir=args.output_dir,
            task_prefix=args.task_prefix,
        )

        result = probe["record_video_result"]
        ok = bool(result.get("success")) and bool(probe["file_exists"]) and bool(probe["path_prefix_ok"])
        if ok:
            print(
                f"[ok] task={probe['task_id']} elapsed={probe['elapsed_sec']}s "
                f"file={result.get('file_path')} size={probe['file_size_bytes']}"
            )
        else:
            any_fail = True
            print(f"[error] task={probe['task_id']} failed")
            print(json.dumps(probe, ensure_ascii=False, indent=2))
            if not args.continue_on_fail:
                break
        print()

    if any_fail:
        print("[done] probe finished with failures", file=sys.stderr)
        return 1

    print("[done] all RTSP probes succeeded")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

