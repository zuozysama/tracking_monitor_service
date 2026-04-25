# media_demo

用于验证“到达推荐点后，服务通过 `MEDIA_RTSP_URL` 拉流并保存截图/视频”。

## Scripts

- `send_task_media_tracking.sh`
  创建开启光电联动与媒体参数的 tracking 任务。
- `drive_to_recommended_point.sh`
  轮询推荐点并连续注入本船导航，模拟到达推荐点。
- `check_media_saved.sh`
  轮询媒体日志，确认当前任务至少生成 1 条成功截图和 1 条成功视频记录。
- `run_media_capture_scene.sh`
  一键执行完整流程（navigation -> perception -> create task -> arrival -> check logs）。

## Usage

```bash
# 直接跑一键场景
bash Linux_demo/media_demo/run_media_capture_scene.sh

# 指定任务 ID
TASK_ID=task-media-demo-1001 \
bash Linux_demo/media_demo/run_media_capture_scene.sh

# 如果当前 shell 看不到 /app/media，可指定本地映射目录用于文件存在性校验
MEDIA_LOCAL_DIR=./artifacts/media \
bash Linux_demo/media_demo/run_media_capture_scene.sh

# 结束后自动终止任务
TERMINATE_AFTER=true \
bash Linux_demo/media_demo/run_media_capture_scene.sh
```

## Env

- `BASE_URL` 默认 `http://0.0.0.0:80`
- `TASK_ID` 默认 `task-media-demo-001`
- `PHOTO_INTERVAL_SEC` 默认 `3`
- `VIDEO_INTERVAL_SEC` 默认 `6`
- `VIDEO_DURATION_SEC` 默认 `4`
- `WAIT_TIMEOUT_SEC` 默认 `90`
- `MEDIA_LOCAL_DIR` 默认 `/app/media`（可改为 `./artifacts/media`）

## Expected

- `GET /mock/collaboration/media/photos` 中出现当前 `task_id` 且 `saved_local=true`
- `GET /mock/collaboration/media/videos` 中出现当前 `task_id` 且 `saved_local=true`
- 日志中的 `file_path` 指向 `/app/media/...`
