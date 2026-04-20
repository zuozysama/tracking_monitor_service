# Linux Demo Task Scripts

`Linux_demo/task` 目录下提供按任务类型拆分的下发脚本，结构参考 `Linux_demo/send_task_tracking.sh`。

## 脚本列表

- `send_task_patrol.sh`
- `send_task_escort.sh`
- `send_task_intercept.sh`
- `send_task_expel.sh`
- `send_task_underwater_search.sh`
- `send_task_fixed_tracking.sh`
- `send_task_preplan.sh`
- `query_task_status_output.sh`

## 使用方式

```bash
# 直接使用默认 TASK_ID（简化命名）
bash Linux_demo/task/send_task_patrol.sh

# 指定 TASK_ID
TASK_ID=escort-2 bash Linux_demo/task/send_task_escort.sh

# 指定 BASE_URL + TASK_ID
BASE_URL=http://0.0.0.0:80 TASK_ID=preplan-3 bash Linux_demo/task/send_task_preplan.sh

# 查询任务状态和输出
TASK_ID=preplan-3 bash Linux_demo/task/query_task_status_output.sh

# 也可用位置参数传入 TASK_ID
bash Linux_demo/task/query_task_status_output.sh preplan-3

# 需要时可附加查询 /result
INCLUDE_RESULT=true TASK_ID=preplan-3 bash Linux_demo/task/query_task_status_output.sh
```

## 说明

- 默认 `BASE_URL`：`http://0.0.0.0:80`
- 所有涉及 `task_area` 的脚本，统一使用以下矩形点位（`polygon`）：

```json
"points": [
  { "longitude": 124.20, "latitude": 21.53 },
  { "longitude": 124.79, "latitude": 21.53 },
  { "longitude": 124.20, "latitude": 21.30 },
  { "longitude": 124.79, "latitude": 21.30 }
]
```

- `fixed_tracking` 按接口约束必须使用 `area_type=point`，因此使用上面第一个点位作为锚点。
