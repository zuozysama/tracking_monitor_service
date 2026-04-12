#!/usr/bin/env sh
set -eu

SDK_ROOT="${DDS_SDK_ROOT:-/app/thirdparty/ljdds/DDSCore3.0.1}"
SDK_ARCH_DIR="${DDS_SDK_ARCH_DIR:-ft2000KylinV10GFgcc9.3.0}"
LIB_DIR="${DDS_LIB_DIR:-${SDK_ROOT}/lib/${SDK_ARCH_DIR}}"
QOS_FILE="${DDS_QOS_FILE:-${SDK_ROOT}/qosconf/example.xml}"
LICENSE_FILE="${DDS_LICENSE_FILE:-${SDK_ROOT}/ljddslicense.lic}"
PORT="${PORT:-80}"

if [ ! -d "${LIB_DIR}" ]; then
  echo "[entrypoint] DDS lib dir not found: ${LIB_DIR}"
  exit 1
fi

if [ ! -f "${QOS_FILE}" ]; then
  echo "[entrypoint] DDS qos file not found: ${QOS_FILE}"
  exit 1
fi

if [ ! -f "${LICENSE_FILE}" ]; then
  echo "[entrypoint] DDS license file not found: ${LICENSE_FILE}"
  exit 1
fi

if ! python -c "import ljdds_python" >/dev/null 2>&1; then
  echo "[entrypoint] ljdds_python is not installed. Check image build stage."
  exit 1
fi

export LD_LIBRARY_PATH="${LIB_DIR}:${LD_LIBRARY_PATH:-}"
export DDS_MODE="${DDS_MODE:-real}"
export DDS_PLATFORM="${DDS_PLATFORM:-linux}"
export DDS_QOS_FILE="${QOS_FILE}"
export DDS_LICENSE_FILE="${LICENSE_FILE}"
export LJDDSHOME="${LJDDSHOME:-${SDK_ROOT}}"
export LJDDS_HOME="${LJDDS_HOME:-${SDK_ROOT}}"

echo "[entrypoint] DDS_MODE=${DDS_MODE}"
echo "[entrypoint] DDS_PLATFORM=${DDS_PLATFORM}"
echo "[entrypoint] DDS_QOS_FILE=${DDS_QOS_FILE}"
echo "[entrypoint] DDS_LICENSE_FILE=${DDS_LICENSE_FILE}"
echo "[entrypoint] LD_LIBRARY_PATH=${LD_LIBRARY_PATH}"
echo "[entrypoint] app port=${PORT}"

exec uvicorn app:app --host 0.0.0.0 --port "${PORT}"
