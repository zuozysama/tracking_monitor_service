# YAML 配置说明

当前服务通过 `config/service_settings.yaml` 读取配置。

## 默认行为
如果不改配置，四个协同服务都走 `mock` 模式：

- optronic
- media
- planning
- sonar

## 切换某个服务到真实 HTTP
例如只切光电服务：

```yaml
external_services:
  optronic:
    mode: http
    base_url: "http://127.0.0.1:9001"
    timeout_sec: 3.0

  media:
    mode: http
    base_url: "http://127.0.0.1:9002"
    timeout_sec: 3.0

  planning:
    mode: http
    base_url: "http://127.0.0.1:9003"
    timeout_sec: 3.0

  sonar:
    mode: http
    base_url: "http://127.0.0.1:9004"
    timeout_sec: 3.0

## DDS 适配层配置

新增 `config/dds_settings.yaml` 用于 DDS 运行模式切换：

- `runtime.mode: mock|real`
- `runtime.platform: win|linux`（`ft2000` 兼容映射为 `linux`）
- `runtime.domain_id`
- `runtime.qos_file`
- `runtime.license_file`
- `runtime.participant_name`

运行时可用环境变量覆盖：

- `DDS_MODE`
- `DDS_PLATFORM`
- `DDS_DOMAIN_ID`
- `DDS_QOS_FILE`
- `DDS_LICENSE_FILE`
- `DDS_PARTICIPANT_NAME`
