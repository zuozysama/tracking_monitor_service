# manual_demo

这个目录只保留两类脚本：
- 查看 DDS 发布信息
- 查询 manual_selection / manual_switch 请求

并保留了“下发两种场景任务”的脚本（不包含态势注入与反馈下发）。

默认服务地址：`http://0.0.0.0:80`（可通过 `BASE_URL` 覆盖）。

## 1) 查看 DDS 发布信息

```bash
# 查看全部 publish 日志
bash Linux_demo/manual_demo/check_manual_dds_publish.sh

# 按 topic 过滤
TOPIC=cc_cm_tracking_monitor_service.v1.manual_selection_request_topic \
bash Linux_demo/manual_demo/check_manual_dds_publish.sh

TOPIC=cc_cm_tracking_monitor_service.v1.manual_switch_request_topic \
bash Linux_demo/manual_demo/check_manual_dds_publish.sh
```

## 2) 查询筛选/切换请求

```bash
# 等待并打印最新 manual_selection 请求
TASK_ID=<task_id> bash Linux_demo/manual_demo/wait_manual_selection_request.sh

# 等待并打印最新 manual_switch 请求
TASK_ID=<task_id> bash Linux_demo/manual_demo/wait_manual_switch_request.sh
```

## 3) 下发两种场景任务

```bash
# manual_selection 场景：不指定目标，等待系统发布 manual_selection_request
TASK_ID=manual-selection-001 \
bash Linux_demo/manual_demo/send_task_manual_selection_scene.sh

# manual_switch 场景：指定目标，等待系统发布 manual_switch_request
TASK_ID=manual-switch-001 DESIGNATED_TARGET_ID=target-001 \
bash Linux_demo/manual_demo/send_task_manual_switch_scene.sh
```

说明：
- 态势（本船/目标）请在你的仿真平台配置后再执行上述脚本。
- `manual_switch` 场景需要 `DESIGNATED_TARGET_ID` 在当前态势中可被跟踪，否则不会进入切换请求流程。
