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
