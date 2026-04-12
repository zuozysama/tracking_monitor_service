param(
  [string]$TaskId = "task-tracking-e2e-001",
  [string]$BaseUrl = "http://127.0.0.1:8080"
)

$ErrorActionPreference = "Stop"

Write-Host "[1/4] health check..."
$health = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/healthz"
if ($health.code -ne 200) {
  throw "health check failed: $($health | ConvertTo-Json -Depth 6)"
}

Write-Host "[2/4] create tracking task..."
$createBody = @{
  task_id = $TaskId
  task_type = "tracking"
  mode = "escort"
  task_area = @{
    area_type = "polygon"
    points = @(
      @{longitude=121.49; latitude=31.21},
      @{longitude=121.52; latitude=31.21},
      @{longitude=121.52; latitude=31.23}
    )
  }
  end_condition = @{ duration_sec = 300 }
} | ConvertTo-Json -Depth 10 -Compress

try {
  $create = Invoke-RestMethod -Method Post -Uri "$BaseUrl/api/v1/tasks" -ContentType "application/json" -Body $createBody
} catch {
  # task may already exist; continue with query stage
  Write-Host "create returned error, continue to query existing task: $($_.Exception.Message)"
}

Start-Sleep -Seconds 2

Write-Host "[3/4] query status/output..."
$status = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/tasks/$TaskId/status"
$output = Invoke-RestMethod -Method Get -Uri "$BaseUrl/api/v1/tasks/$TaskId/output"

Write-Host "[4/4] query dds publish logs..."
$logs = Invoke-RestMethod -Method Get -Uri "$BaseUrl/mock/collaboration/dds/publish-logs"
$topics = @()
if ($logs.data -and $logs.data.items) {
  $topics = $logs.data.items | Select-Object -ExpandProperty topic -Unique
}

$result = [pscustomobject]@{
  task_id = $TaskId
  task_status = $status.data.task_status
  execution_phase = $status.data.execution_phase
  output_type = $output.data.output_type
  dds_log_count = if ($logs.data -and $logs.data.items) { ($logs.data.items | Measure-Object).Count } else { 0 }
  dds_topics = $topics
  dds_last = if ($logs.data -and $logs.data.items) { ($logs.data.items | Select-Object -Last 10) } else { @() }
}

$result | ConvertTo-Json -Depth 12
