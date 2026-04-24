#!/usr/bin/env bash
# 在有网络的环境下执行，将依赖下载到 offline_deps/，供 Dockerfile.local 离线构建使用。
#
# 务必使用与 backend/Dockerfile 相同的 Python 版本（当前为 3.12）。
# 若使用 3.13+，grpcio 等可能没有对应 wheel，pip 会拉 .tar.gz 并尝试源码编译，
# 需要系统安装 g++，且容易失败。可指定解释器：
#   PIP_DOWNLOAD_PYTHON=/path/to/python3.12 ./scripts/download_offline_wheels.sh
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p offline_deps

if [ -n "${PIP_DOWNLOAD_PYTHON:-}" ]; then
  PY="${PIP_DOWNLOAD_PYTHON}"
elif command -v python3.12 >/dev/null 2>&1; then
  PY=python3.12
else
  PY=python3
  ver="$("$PY" -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")' 2>/dev/null || echo "?")"
  if [ "$ver" != "3.12" ]; then
    echo "warning: 当前 pip 对应 Python ${ver}，而 Docker 使用 3.12。" >&2
    echo "  grpcio/pymilvus 易触发源码编译并缺少 c++。请安装 python3.12 后重试，或设置 PIP_DOWNLOAD_PYTHON。" >&2
  fi
fi

"$PY" -m pip download \
  -r requirements.txt \
  -r requirements-docker-local-extras.txt \
  -d offline_deps
echo "Done. Wheels under $(pwd)/offline_deps (interpreter: $PY)"
