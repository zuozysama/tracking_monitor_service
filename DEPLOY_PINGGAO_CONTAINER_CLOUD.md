# Pinggao Container Cloud Deployment (DDS Built-in Image)

## 1) Scope

This repo now supports a minimal deploy package with:

- Default base image: `python:3.9-slim`
- Optional cloud base image: `cc-me-formation:dds-arm64-slim` (via build arg)
- Arch: `linux/arm64`
- Entrypoint: `/app/docker-entrypoint-dds.sh`
- Service port in container: `80`

The image already contains:

- DDS Python wheel: `ljdds_python-3.0.1-py3-none-any.whl`
- DDS runtime `.so` files
- Default QoS file: `/opt/ljdds/DDSCore3.0.1/qosconf/example.xml`
- Default license file: `/opt/ljdds/DDSCore3.0.1/ljddslicense.lic`

## 2) Build Image

```bash
docker build -t cc_cm_tracking_monitor_service:real .
```

Use cloud base image when needed:

```bash
docker build --build-arg BASE_IMAGE=cc-me-formation:dds-arm64-slim -t cc_cm_tracking_monitor_service:real .
```

## 3) Container Cloud UI Settings

### Startup command

- Command: `sh`
- Args: `/app/docker-entrypoint-dds.sh`

### Port mapping

- Container port: `80`
- Service/ingress port: use your platform rule (for example `80`)

### Required environment variables

- `PORT=80`
- `DDS_MODE=real`
- `DDS_PLATFORM=linux`
- `DDS_CONFIG_PATH=/app/config/dds_settings.yaml`
- `DDS_QOS_FILE=/opt/ljdds/DDSCore3.0.1/qosconf/example.xml`
- `DDS_LICENSE_FILE=/opt/ljdds/DDSCore3.0.1/ljddslicense.lic`
- `DDS_LIB_DIR=/opt/ljdds/DDSCore3.0.1/lib/ft2000KylinV10GFgcc9.3.0`

### Optional environment variables (normally keep default)

- `DDS_SDK_ROOT=/opt/ljdds/DDSCore3.0.1`
- `DDS_SDK_ARCH_DIR=ft2000KylinV10GFgcc9.3.0`
- `LJDDSHOME=/opt/ljdds/DDSCore3.0.1`
- `LJDDS_HOME=/opt/ljdds/DDSCore3.0.1`

### Volume mounts

- Config dir (read-only): `<platform-config-dir> -> /app/config`
- Media output dir (read-write): `<platform-data-dir> -> /app/artifacts/media`

Do not mount `/opt/ljdds`; DDS is already built into the image.

## 4) Override QoS or License at Runtime

If production needs a different QoS/license file, mount files into `/app/config` and override:

- `DDS_QOS_FILE=/app/config/xxx.xml`
- `DDS_LICENSE_FILE=/app/config/xxx.lic`

