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

