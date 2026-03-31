# Tracking Monitor Service

跟踪监视服务原型工程。当前版本以 `FastAPI + mock DDS/mock 外部服务` 的方式运行，目标是先与《W5-附件1-跟踪监视服务v1》中的接口口径对齐，便于 Windows 环境联调；后续再进一步整理 Docker 与麒麟系统部署方案。

## 当前状态

- 已按文档补齐或对齐主要 REST 接口
- DDS 相关暂未接入真实中间件，统一用 mock 接口代替
- 已支持任务类型：
  - `patrol`
  - `tracking`
  - `fixed_tracking`
  - `underwater_search`
  - `preplan`
- 任务执行采用后台决策循环，每秒刷新一次任务状态与输出

## 技术栈

- Python 3.9+
- FastAPI
- Uvicorn
- Pydantic v2
- PyYAML

依赖见 [requirements.txt](E:/projects/tracking_monitor_service/requirements.txt)。

## 启动方式

先安装依赖：

```bash
pip install -r requirements.txt
```

启动服务：

```bash
uvicorn app:app --reload --host 0.0.0.0 --port 8080
```

启动后可访问：

- Swagger UI: [http://127.0.0.1:8080/docs](http://127.0.0.1:8080/docs)
- OpenAPI JSON: [http://127.0.0.1:8080/openapi.json](http://127.0.0.1:8080/openapi.json)

## 项目结构

- [app.py](E:/projects/tracking_monitor_service/app.py): 应用入口
- [api/task_api.py](E:/projects/tracking_monitor_service/api/task_api.py): 任务创建、终止、状态、输出接口
- [api/spec_api.py](E:/projects/tracking_monitor_service/api/spec_api.py): 文档新增接口，如媒体接入、人工筛选/切换、声纳查询
- [api/mock_dds_api.py](E:/projects/tracking_monitor_service/api/mock_dds_api.py): mock DDS 输入接口
- [api/mock_collaboration_api.py](E:/projects/tracking_monitor_service/api/mock_collaboration_api.py): mock 协同状态与日志查看接口
- [api/mock_autonomy_api.py](E:/projects/tracking_monitor_service/api/mock_autonomy_api.py): mock 自主航行下发结果查看接口
- [services/task_service.py](E:/projects/tracking_monitor_service/services/task_service.py): 任务主流程
- [services/collaboration_service.py](E:/projects/tracking_monitor_service/services/collaboration_service.py): mock 联动、规划上报、自主航行下发
- [domain/models.py](E:/projects/tracking_monitor_service/domain/models.py): 领域模型与接口模型
- [store/](E:/projects/tracking_monitor_service/store): 当前为内存存储

## 已对齐接口

### 控制类接口

- `POST /tasks`
- `POST /tasks/{task_id}/terminate`
- `POST /media/stream/access`
- `POST /tasks/manual-selection/request`
- `POST /tasks/manual-switch/request`
- `POST /tasks/manual-selection/feedback`
- `POST /tasks/manual-switch/feedback`

### 状态类接口

- `GET /tasks/{task_id}/status`
- `GET /tasks/{task_id}/output`
- `GET /tasks/{task_id}/result`
- `GET /sonar/match/status?task_id=...`

### mock DDS 输入接口

- `POST /mock/dds/navigation`
- `POST /mock/dds/perception`
- 兼容保留：
  - `POST /mock/dds/ownship`
  - `POST /mock/dds/targets`

### mock 观测接口

- `GET /mock/collaboration/planning/stages`
- `GET /mock/collaboration/planning/plans`
- `GET /mock/collaboration/media/photos`
- `GET /mock/collaboration/media/videos`
- `GET /mock/collaboration/media/stream-access`
- `GET /mock/collaboration/manual-selection/requests`
- `GET /mock/collaboration/manual-switch/requests`
- `GET /mock/collaboration/manual-selection/feedbacks`
- `GET /mock/collaboration/manual-switch/feedbacks`
- `GET /mock/autonomy/patrol/logs`
- `GET /mock/autonomy/tracking/logs`

## 联调说明

当前版本中，文档里的 DDS 交互改为通过 HTTP mock 接口模拟：

- 本船导航态势 DDS
  - 使用 `POST /mock/dds/navigation`
- 目标感知 DDS
  - 使用 `POST /mock/dds/perception`
- 任务执行进度 DDS 上报
  - 通过 `GET /mock/collaboration/planning/stages` 查看
- 任务方案 DDS 上报
  - 通过 `GET /mock/collaboration/planning/plans` 查看
- 自主航行服务下发结果
  - 通过 `GET /mock/autonomy/patrol/logs`
  - 或 `GET /mock/autonomy/tracking/logs` 查看

## 推荐调试顺序

### 1. 重置 mock 态势

```bash
curl -X POST http://127.0.0.1:8080/mock/dds/reset
```

### 2. 注入本船导航态势

```bash
curl -X POST http://127.0.0.1:8080/mock/dds/navigation \
  -H "Content-Type: application/json" \
  -d '{
    "platform_id": 1001,
    "speed_mps": 6.2,
    "heading_deg": 90.0,
    "longitude": 121.5000000,
    "latitude": 31.2200000,
    "timestamp": "2026-03-24T10:00:00Z"
  }'
```

### 3. 注入目标感知数据

```bash
curl -X POST http://127.0.0.1:8080/mock/dds/perception \
  -H "Content-Type: application/json" \
  -d '{
    "target_count": 1,
    "targets": [
      {
        "source_platform_id": 2001,
        "target_id": "target-001",
        "target_batch_no": 1,
        "target_bearing_deg": 35.0,
        "target_distance_m": 3000,
        "target_absolute_speed_mps": 6.2,
        "target_absolute_heading_deg": 90.0,
        "target_longitude": 121.5030000,
        "target_latitude": 31.2200000,
        "target_type_code": 106,
        "military_civil_attr": 1,
        "target_name": "目标001",
        "threat_level": 2,
        "timestamp": "2026-03-24T10:00:00Z",
        "active": true
      }
    ]
  }'
```

### 4. 创建任务

#### 4.1 跟踪任务示例

```bash
curl -X POST http://127.0.0.1:8080/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task-tracking-001",
    "task_type": "tracking",
    "task_name": "伴随测试任务",
    "task_source": "planning_service",
    "priority": 1,
    "mode": "escort",
    "target_info": {
      "target_id": "target-001",
      "target_batch_no": 1,
      "target_type_code": 106,
      "threat_level": 2,
      "target_name": "目标001",
      "military_civil_attr": 1
    },
    "task_area": {
      "area_type": "polygon",
      "points": [
        { "longitude": 121.49, "latitude": 31.21 },
        { "longitude": 121.52, "latitude": 31.21 },
        { "longitude": 121.52, "latitude": 31.23 },
        { "longitude": 121.49, "latitude": 31.23 }
      ]
    },
    "expected_speed": 12.0,
    "update_interval_sec": 1,
    "end_condition": {
      "duration_sec": 300,
      "out_of_region_finish": true
    },
    "stream_media_param": {
      "photo_enabled": true,
      "photo_interval_sec": 5,
      "video_enabled": true,
      "video_interval_sec": 10,
      "video_duration_sec": 10
    },
    "linkage_param": {
      "enable_optical": true,
      "enable_evidence": true
    }
  }'
```

#### 4.2 预规划任务示例

```bash
curl -X POST http://127.0.0.1:8080/tasks \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task-preplan-001",
    "task_type": "preplan",
    "task_name": "预规划测试任务",
    "task_area": {
      "area_type": "polygon",
      "points": [
        { "longitude": 121.49, "latitude": 31.21 },
        { "longitude": 121.52, "latitude": 31.21 },
        { "longitude": 121.52, "latitude": 31.23 },
        { "longitude": 121.49, "latitude": 31.23 }
      ]
    },
    "expected_speed": 10.0,
    "end_condition": {
      "duration_sec": 120
    }
  }'
```

### 5. 查询状态与正式输出

```bash
curl http://127.0.0.1:8080/tasks/task-tracking-001/status
curl http://127.0.0.1:8080/tasks/task-tracking-001/output
curl http://127.0.0.1:8080/tasks/task-tracking-001/result
```

### 6. 查看 mock 规划上报与自主航行下发

```bash
curl http://127.0.0.1:8080/mock/collaboration/planning/stages
curl http://127.0.0.1:8080/mock/collaboration/planning/plans
curl http://127.0.0.1:8080/mock/autonomy/tracking/logs
```

## 其他接口调试示例

### 终止任务

```bash
curl -X POST http://127.0.0.1:8080/tasks/task-tracking-001/terminate \
  -H "Content-Type: application/json" \
  -d '{
    "reason": "swagger手动结束测试"
  }'
```

### 获取视频流接入信息

```bash
curl -X POST http://127.0.0.1:8080/media/stream/access \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task-tracking-001",
    "stream_type": "optical_video",
    "channel_id": "optical-001",
    "media_protocol": "webrtc",
    "request_time": "2026-03-24T10:01:20Z"
  }'
```

### 发起人工筛选请求

```bash
curl -X POST http://127.0.0.1:8080/tasks/manual-selection/request \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task-tracking-001",
    "request_type": "manual_selection",
    "timeout_sec": 10,
    "candidate_targets": [
      {
        "target_id": "target-001",
        "target_batch_no": 1,
        "target_type_code": 106,
        "threat_level": 2,
        "target_name": "目标001",
        "military_civil_attr": 1
      },
      {
        "target_id": "target-002",
        "target_batch_no": 2,
        "target_type_code": 108,
        "threat_level": 3,
        "target_name": "目标002",
        "military_civil_attr": 1
      }
    ]
  }'
```

### 提交人工筛选反馈

```bash
curl -X POST http://127.0.0.1:8080/tasks/manual-selection/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task-tracking-001",
    "selected_target_id": "target-002",
    "feedback_time": "2026-03-24T10:02:30Z"
  }'
```

### 发起人工切换请求

```bash
curl -X POST http://127.0.0.1:8080/tasks/manual-switch/request \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task-tracking-001",
    "request_type": "manual_switch",
    "timeout_sec": 10,
    "current_target_id": "target-001",
    "new_candidate_targets": [
      {
        "target_id": "target-003",
        "target_batch_no": 3,
        "target_type_code": 106,
        "threat_level": 2,
        "target_name": "目标003",
        "military_civil_attr": 1
      }
    ]
  }'
```

### 提交人工切换反馈

```bash
curl -X POST http://127.0.0.1:8080/tasks/manual-switch/feedback \
  -H "Content-Type: application/json" \
  -d '{
    "task_id": "task-tracking-001",
    "selected_target_id": "target-003",
    "keep_current": false,
    "feedback_time": "2026-03-24T10:03:00Z"
  }'
```

### 查询声纳匹配状态

```bash
curl "http://127.0.0.1:8080/sonar/match/status?task_id=task-underwater-001"
```

### 设置 mock 声纳状态

```bash
curl -X POST http://127.0.0.1:8080/mock/collaboration/sonar/task-underwater-001/status \
  -H "Content-Type: application/json" \
  -d '{
    "matched": false,
    "confidence": 0.2,
    "update_time": "2026-03-24T10:06:00Z"
  }'
```

## PowerShell 调试示例

如果在 Windows PowerShell 里调试，推荐用：

```powershell
$body = @{
  task_id = "task-preplan-001"
  task_type = "preplan"
  task_area = @{
    area_type = "polygon"
    points = @(
      @{ longitude = 121.49; latitude = 31.21 }
      @{ longitude = 121.52; latitude = 31.21 }
      @{ longitude = 121.52; latitude = 31.23 }
      @{ longitude = 121.49; latitude = 31.23 }
    )
  }
  expected_speed = 10.0
} | ConvertTo-Json -Depth 10

Invoke-RestMethod `
  -Uri "http://127.0.0.1:8080/tasks" `
  -Method Post `
  -ContentType "application/json" `
  -Body $body
```

另外也提供了两份可直接执行的联调脚本：

- HTTP Client 脚本: [examples/tracking_monitor_local.http](E:/projects/tracking_monitor_service/examples/tracking_monitor_local.http)
- PowerShell 一键联调脚本: [scripts/tracking_monitor_demo.ps1](E:/projects/tracking_monitor_service/scripts/tracking_monitor_demo.ps1)

## 当前已知说明

- 当前为内存存储，服务重启后任务、态势、联调日志会丢失
- 当前未接真实 DDS SDK，仅通过 mock HTTP 接口模拟 DDS 输入输出
- 当前更侧重接口联调与功能对齐，不是生产部署版本
- 文档中的部分接口语义在“本服务提供接口”和“本服务调用外部接口”之间存在交叉，当前实现优先保证字段和联调流程可用

## 后续建议

- 补充真实 DDS 适配层，替换 `mock/dds`
- 将 mock 日志持久化到 Redis 或数据库
- 增加接口测试用例与任务场景回归测试
- 增加 Dockerfile、启动脚本和麒麟系统部署说明
