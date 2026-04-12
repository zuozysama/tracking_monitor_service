ARG BASE_IMAGE=python:3.9-slim
FROM ${BASE_IMAGE}

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple \
    DDS_MODE=real \
    DDS_PLATFORM=linux \
    DDS_CONFIG_PATH=/app/config/dds_settings.yaml \
    DDS_SDK_ROOT=/app/thirdparty/ljdds/DDSCore3.0.1 \
    DDS_SDK_ARCH_DIR=ft2000KylinV10GFgcc9.3.0 \
    DDS_QOS_FILE=/app/thirdparty/ljdds/DDSCore3.0.1/qosconf/example.xml \
    DDS_LICENSE_FILE=/app/thirdparty/ljdds/DDSCore3.0.1/ljddslicense.lic \
    DDS_LIB_DIR=/app/thirdparty/ljdds/DDSCore3.0.1/lib/ft2000KylinV10GFgcc9.3.0 \
    LJDDSHOME=/app/thirdparty/ljdds/DDSCore3.0.1 \
    LJDDS_HOME=/app/thirdparty/ljdds/DDSCore3.0.1 \
    FFMPEG_BIN=ffmpeg \
    MEDIA_OUTPUT_DIR=artifacts/media \
    PORT=80 \
    LJDDS_DOCKER_LIC=1

RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g; s|http://security.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list; \
    fi; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i 's|http://deb.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g; s|http://security.debian.org|https://mirrors.tuna.tsinghua.edu.cn|g' /etc/apt/sources.list.d/debian.sources; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends ffmpeg vim nano iputils-ping build-essential curl ca-certificates; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

COPY . /app
COPY LJDDS /app/thirdparty/ljdds

RUN set -eux; \
    pip install "/app/thirdparty/ljdds/ljdds_python-3.0.1-py3-none-any.whl"; \
    chmod +x /app/docker-entrypoint-dds.sh

EXPOSE 80

CMD ["sh", "/app/docker-entrypoint-dds.sh"]
