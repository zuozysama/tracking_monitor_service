import os
import shutil
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from clients.media_client import MediaClient


class MediaClientVideoEnvTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self._old_env = {
            "MEDIA_VIDEO_TARGET_WIDTH": os.environ.get("MEDIA_VIDEO_TARGET_WIDTH"),
            "MEDIA_VIDEO_TARGET_HEIGHT": os.environ.get("MEDIA_VIDEO_TARGET_HEIGHT"),
            "MEDIA_VIDEO_KEEP_AUDIO": os.environ.get("MEDIA_VIDEO_KEEP_AUDIO"),
            "MEDIA_VIDEO_PRESET": os.environ.get("MEDIA_VIDEO_PRESET"),
        }

    def tearDown(self) -> None:
        for key, value in self._old_env.items():
            if value is None:
                os.environ.pop(key, None)
            else:
                os.environ[key] = value

    def test_record_video_uses_env_resolution_and_audio_switch(self):
        os.environ["MEDIA_VIDEO_TARGET_WIDTH"] = "1280"
        os.environ["MEDIA_VIDEO_TARGET_HEIGHT"] = "720"
        os.environ["MEDIA_VIDEO_KEEP_AUDIO"] = "false"
        os.environ["MEDIA_VIDEO_PRESET"] = "ultrafast"

        client = MediaClient()
        captured_cmd: list[str] = []

        def _fake_run_ffmpeg(cmd: list[str], timeout_sec: int = 30):
            captured_cmd.extend(cmd)
            return False, "mock error"

        tmp_root = Path(".tmp_media_env_test")
        tmp_root.mkdir(parents=True, exist_ok=True)
        tmpdir = tempfile.mkdtemp(dir=str(tmp_root))
        try:
            with patch.object(MediaClient, "_resolve_stream_url", return_value="rtsp://example/stream"), patch.object(
                MediaClient, "_task_output_dir", return_value=Path(tmpdir)
            ), patch.object(MediaClient, "_run_ffmpeg", side_effect=_fake_run_ffmpeg):
                result = client.record_video(task_id="task-test", duration_sec=4)
        finally:
            shutil.rmtree(tmpdir, ignore_errors=True)
            shutil.rmtree(tmp_root, ignore_errors=True)

        self.assertFalse(result["success"])
        self.assertIn("-vf", captured_cmd)
        self.assertIn("scale=1280:720", captured_cmd)
        self.assertIn("-preset", captured_cmd)
        self.assertIn("ultrafast", captured_cmd)
        self.assertIn("-an", captured_cmd)
        self.assertNotIn("-c:a", captured_cmd)


if __name__ == "__main__":
    unittest.main()
