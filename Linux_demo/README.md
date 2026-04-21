# Linux Demo Scripts (HTTP-style)

这组脚本按 `.http` 的使用思路设计：
- 每个脚本里是固定 JSON 请求体
- 每执行一次脚本，就发送一次请求（相当于点一次 Send）

## Core Scripts

- `send_task_tracking.sh`:
  发送一次创建 tracking 任务请求
- `send_mock_navigation.sh`:
  发送一次 mock 本船导航态势
- `send_mock_perception.sh`:
  发送一次 mock 目标感知态势
- `send_task_terminate.sh`:
  发送一次终止任务请求
- `send_scene_tracking.sh`:
  按顺序发送 3 条请求：navigation -> perception -> create task

## Usage

```bash
# 1) 单条请求：只下发任务
bash Linux_demo/send_task_tracking.sh

# 2) 指定任务ID
TASK_ID=task-tracking-1001 bash Linux_demo/send_task_tracking.sh

# 3) 一键发送场景请求（3条JSON）
bash Linux_demo/send_scene_tracking.sh

# 4) 终止指定任务
TASK_ID=task-tracking-1001 bash Linux_demo/send_task_terminate.sh
```

## Env

- `BASE_URL` 默认 `http://0.0.0.0:80`
- `TASK_ID` 默认 `task-tracking-demo-001`

示例：
```bash
BASE_URL=http://0.0.0.0:80 TASK_ID=task-tracking-2001 bash Linux_demo/send_scene_tracking.sh
```


## Direct set_plan Scripts

These scripts POST directly to autonomy `set_plan`:
- `send_set_plan_patrol.sh`
- `send_set_plan_tracking.sh`
- `send_set_plan_fixed_tracking.sh`
- `send_set_plan_scene.sh` (patrol -> tracking)

Usage:
```bash
# Keep env vars and address consistent with deployment side
EXTERNAL_AUTONOMY_MODE=http \
EXTERNAL_AUTONOMY_URL=172.16.10.104/api/v1/set_plan \
bash Linux_demo/send_set_plan_patrol.sh

EXTERNAL_AUTONOMY_MODE=http \
EXTERNAL_AUTONOMY_URL=172.16.10.104/api/v1/set_plan \
TASK_ID=task-direct-1001 TARGET_ID=target-001 TARGET_BATCH_NO=1 \
bash Linux_demo/send_set_plan_tracking.sh

EXTERNAL_AUTONOMY_MODE=http \
EXTERNAL_AUTONOMY_URL=172.16.10.104/api/v1/set_plan \
bash Linux_demo/send_set_plan_fixed_tracking.sh

EXTERNAL_AUTONOMY_MODE=http \
EXTERNAL_AUTONOMY_URL=172.16.10.104/api/v1/set_plan \
bash Linux_demo/send_set_plan_scene.sh
```

Env used by these scripts:
- `EXTERNAL_AUTONOMY_MODE` (default `http`)
- `EXTERNAL_AUTONOMY_URL` (default `172.16.10.104/api/v1/set_plan`)
- also supports `EXTERNAL_AUTONOMY_BASE_URL` as fallback

Optional params:
- patrol: `TASK_ID`, `MAX_SPEED`, `END_TIME`
- tracking: `TASK_ID`, `TARGET_ID`, `TARGET_BATCH_NO`, `REL_RANGE_M`, `RELATIVE_BEARING_DEG`, `MAX_SPEED`
- fixed-tracking: `TASK_ID`, `MAX_SPEED`
- scene: `SLEEP_SEC`

> Note: set_plan demo scripts have been moved to `Linux_demo/autonomy_demo/`.
>
> Use:
> - `bash Linux_demo/autonomy_demo/send_set_plan_patrol.sh`
> - `bash Linux_demo/autonomy_demo/send_set_plan_tracking.sh`
> - `bash Linux_demo/autonomy_demo/send_set_plan_fixed_tracking.sh`
> - `bash Linux_demo/autonomy_demo/send_set_plan_scene.sh`

> Default endpoint in scripts is now `172.16.10.104:8000`.
> You can still override it via `EXTERNAL_AUTONOMY_URL` (or `EXTERNAL_AUTONOMY_BASE_URL`).
