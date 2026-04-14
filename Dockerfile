ARG BASE_IMAGE=python:3.9-slim
FROM ${BASE_IMAGE}

WORKDIR /app

ARG APT_MIRROR=https://mirrors.tuna.tsinghua.edu.cn
ARG PIP_INDEX_URL=https://pypi.tuna.tsinghua.edu.cn/simple

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

RUN set -eux; \
    if [ -f /etc/apt/sources.list ]; then \
      sed -i "s|http://deb.debian.org|${APT_MIRROR}|g; s|http://security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list; \
    fi; \
    if [ -f /etc/apt/sources.list.d/debian.sources ]; then \
      sed -i "s|http://deb.debian.org|${APT_MIRROR}|g; s|http://security.debian.org|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources; \
    fi; \
    apt-get update; \
    apt-get install -y --no-install-recommends ffmpeg vim nano iputils-ping build-essential curl ca-certificates procps psmisc net-tools; \
    rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN python -m pip install --upgrade pip setuptools wheel && \
    pip install -i "${PIP_INDEX_URL}" -r requirements.txt

COPY . /app
COPY LJDDS /app/thirdparty/ljdds

RUN set -eux; \
    find /app -type f -name "*.sh" -exec sed -i 's/\r$//' {} +; \
    find /app/thirdparty/ljdds -type f \( -name "*.sh" -o -name "*.ini" -o -name "*.xml" -o -name "*.conf" \) -exec sed -i 's/\r$//' {} +; \
    pip install "/app/thirdparty/ljdds/ljdds_python-3.0.1-py3-none-any.whl"; \
    chmod +x /app/docker-entrypoint-dds.sh; \
    find /app -type f -name "*.sh" -exec chmod +x {} +

# Runtime envs for cloud deployment:
# Prefer setting these manually in Pinggao Cloud:
# PORT, DDS_MODE, DDS_PLATFORM, DDS_CONFIG_PATH, DDS_SDK_ROOT,
# DDS_SDK_ARCH_DIR, DDS_QOS_FILE, DDS_LICENSE_FILE, DDS_LIB_DIR,
# LJDDSHOME, LJDDS_HOME, FFMPEG_BIN, MEDIA_OUTPUT_DIR, LJDDS_DOCKER_LIC
ENV PORT=80

EXPOSE 80

CMD ["sh", "/app/docker-entrypoint-dds.sh"]
