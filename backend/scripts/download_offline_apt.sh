#!/usr/bin/env bash
# 在有网络的环境执行：将与 backend/Dockerfile.local 相同基础镜像匹配的 .deb 下载到 offline_deps/apt/
# 供离线构建安装 LibreOffice（.doc 转换）等系统依赖，构建时无需访问 apt 源。
#
# 用法（在 backend 目录）：
#   ./scripts/download_offline_apt.sh
#
# 默认使用阿里云 Debian 镜像（国内 deb.debian.org 常不可用）；需官方源时：
#   APT_MIRROR=http://deb.debian.org/debian ./scripts/download_offline_apt.sh
#
# 可选：与线上一致的基础镜像（默认 python:3.12-slim）
#   BASE_IMAGE=192.168.252.252:5566/zs-rag/python:3.12-slim ./scripts/download_offline_apt.sh
set -euo pipefail
cd "$(dirname "$0")/.."
OUT_DIR="$(pwd)/offline_deps/apt"
BASE_IMAGE="${BASE_IMAGE:-python:3.12-slim}"
APT_MIRROR="${APT_MIRROR:-http://mirrors.aliyun.com/debian}"
mkdir -p "$OUT_DIR"

# 清空旧 deb，避免混用不同 Debian 版本的包
rm -f "$OUT_DIR"/*.deb

echo "Downloading apt packages into ${OUT_DIR}"
echo "  base image : ${BASE_IMAGE}"
echo "  apt mirror : ${APT_MIRROR}"

docker run --rm \
  -v "${OUT_DIR}:/out" \
  -e "APT_MIRROR=${APT_MIRROR}" \
  "$BASE_IMAGE" \
  bash -c '
    set -eux
    if [ -n "${APT_MIRROR}" ] && [ -f /etc/apt/sources.list.d/debian.sources ]; then
      sed -i "s|http://deb.debian.org/debian|${APT_MIRROR}|g" /etc/apt/sources.list.d/debian.sources
      sed -i "s|http://deb.debian.org/debian-security|${APT_MIRROR}-security|g" /etc/apt/sources.list.d/debian.sources || true
    fi
    apt-get update
    apt-get install -y --download-only --no-install-recommends \
      -o Dir::Cache::archives=/out \
      libreoffice-writer-nogui \
      libreoffice-java-common \
      ca-certificates
    ls -lh /out/*.deb
  '

count="$(find "$OUT_DIR" -maxdepth 1 -name '*.deb' | wc -l | tr -d ' ')"
if [ "$count" = "0" ]; then
  echo "错误：未下载到任何 .deb。" >&2
  echo "  若 deb.debian.org 不可达，请确认已使用国内镜像（脚本默认 mirrors.aliyun.com）。" >&2
  echo "  也可手动指定：APT_MIRROR=http://mirrors.tuna.tsinghua.edu.cn/debian ./scripts/download_offline_apt.sh" >&2
  exit 1
fi

echo "Done: ${count} deb packages under ${OUT_DIR} ($(du -sh "$OUT_DIR" | cut -f1))"
