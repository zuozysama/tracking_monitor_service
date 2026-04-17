$ErrorActionPreference = "Stop"

$BaseUrl = if ([string]::IsNullOrWhiteSpace($env:BASE_URL)) { "http://0.0.0.0:80" } else { $env:BASE_URL }
$JsonHeader = @("Content-Type: application/json")

function Step($message) {
    Write-Host ""
    Write-Host "== $message ==" -ForegroundColor Cyan
}

function Invoke-JsonGet($url) {
    curl.exe -s $url
    Write-Host ""
}

function Invoke-JsonPost($url, $body) {
    curl.exe -s -X POST $url -H "Content-Type: application/json" -d $body
    Write-Host ""
}

Step "健康检查"
Invoke-JsonGet "$BaseUrl/"

Step "重置 mock DDS 态势"
Invoke-JsonPost "$BaseUrl/mock/dds/reset" "{}"

Step "注入本船导航态势"
$navigation = @'
{
  "platform_id": 1001,
  "speed_mps": 6.2,
  "heading_deg": 90.0,
  "longitude": 121.5000000,
  "latitude": 31.2200000,
  "timestamp": "2026-03-24T10:00:00Z"
}
'@
Invoke-JsonPost "$BaseUrl/mock/dds/navigation" $navigation

Step "注入目标感知数据"
$perception = @'
{
  "target_count": 2,
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
    },
    {
      "source_platform_id": 2001,
      "target_id": "target-002",
      "target_batch_no": 2,
      "target_bearing_deg": 42.0,
      "target_distance_m": 3400,
      "target_absolute_speed_mps": 5.8,
      "target_absolute_heading_deg": 100.0,
      "target_longitude": 121.5060000,
      "target_latitude": 31.2210000,
      "target_type_code": 108,
      "military_civil_attr": 1,
      "target_name": "目标002",
      "threat_level": 3,
      "timestamp": "2026-03-24T10:00:00Z",
      "active": true
    }
  ]
}
'@
Invoke-JsonPost "$BaseUrl/mock/dds/perception" $perception

Step "创建 tracking 任务"
$trackingTask = @'
{
  "task_id": "task-tracking-001",
  "task_type": "escort",
  "task_name": "伴随测试任务",
  "task_source": "planning_service",
  "priority": 1,
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
}
'@
Invoke-JsonPost "$BaseUrl/tasks" $trackingTask

Step "查询 tracking 状态"
Invoke-JsonGet "$BaseUrl/tasks/task-tracking-001/status"

Step "查询 tracking 正式输出"
Invoke-JsonGet "$BaseUrl/tasks/task-tracking-001/output"

Step "获取视频流接入信息"
$streamAccess = @'
{
  "task_id": "task-tracking-001",
  "stream_type": "optical_video",
  "channel_id": "optical-001",
  "media_protocol": "webrtc",
  "request_time": "2026-03-24T10:01:20Z"
}
'@
Invoke-JsonPost "$BaseUrl/media/stream/access" $streamAccess

Step "发起人工筛选请求"
$manualSelectionRequest = @'
{
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
}
'@
Invoke-JsonPost "$BaseUrl/tasks/manual-selection/request" $manualSelectionRequest

Step "提交人工筛选反馈"
$manualSelectionFeedback = @'
{
  "task_id": "task-tracking-001",
  "selected_target_id": "target-002",
  "feedback_time": "2026-03-24T10:02:30Z"
}
'@
Invoke-JsonPost "$BaseUrl/tasks/manual-selection/feedback" $manualSelectionFeedback

Step "发起人工切换请求"
$manualSwitchRequest = @'
{
  "task_id": "task-tracking-001",
  "request_type": "manual_switch",
  "timeout_sec": 10,
  "current_target_id": "target-002",
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
}
'@
Invoke-JsonPost "$BaseUrl/tasks/manual-switch/request" $manualSwitchRequest

Step "提交人工切换反馈"
$manualSwitchFeedback = @'
{
  "task_id": "task-tracking-001",
  "selected_target_id": "target-003",
  "keep_current": false,
  "feedback_time": "2026-03-24T10:03:00Z"
}
'@
Invoke-JsonPost "$BaseUrl/tasks/manual-switch/feedback" $manualSwitchFeedback

Step "查看规划阶段上报日志"
Invoke-JsonGet "$BaseUrl/mock/collaboration/planning/stages"

Step "查看规划方案上报日志"
Invoke-JsonGet "$BaseUrl/mock/collaboration/planning/plans"

Step "查看 tracking 下发日志"
Invoke-JsonGet "$BaseUrl/mock/autonomy/tracking/logs"

Step "创建 preplan 任务"
$preplanTask = @'
{
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
}
'@
Invoke-JsonPost "$BaseUrl/tasks" $preplanTask

Step "查询 preplan 输出"
Invoke-JsonGet "$BaseUrl/tasks/task-preplan-001/output"

Step "设置水下搜索 mock 声纳状态"
$sonarStatus = @'
{
  "matched": false,
  "confidence": 0.2,
  "update_time": "2026-03-24T10:06:00Z"
}
'@
Invoke-JsonPost "$BaseUrl/mock/collaboration/sonar/task-underwater-001/status" $sonarStatus

Step "查询声纳匹配状态"
Invoke-JsonGet "$BaseUrl/sonar/match/status?task_id=task-underwater-001"

Step "终止 tracking 任务"
$terminateBody = @'
{
  "reason": "swagger手动结束测试"
}
'@
Invoke-JsonPost "$BaseUrl/tasks/task-tracking-001/terminate" $terminateBody
