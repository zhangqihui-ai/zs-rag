#!/usr/bin/env bash
# 下载 Temurin JRE 21（Linux x64）到 offline_deps/jre/，供 Dockerfile.local 离线构建使用。
# 需在有网络的环境执行一次；构建机无需访问 deb.debian.org。
set -euo pipefail
cd "$(dirname "$0")/.."
mkdir -p offline_deps/jre

ARCH="${JRE_ARCH:-x64}"
OUT="offline_deps/jre/temurin-21-jre.tar.gz"

if [ -f "$OUT" ] && [ "${FORCE_JRE_DOWNLOAD:-0}" != "1" ]; then
  echo "已存在 $OUT，跳过（FORCE_JRE_DOWNLOAD=1 可强制重下）"
  exit 0
fi

echo "Downloading Temurin 21 JRE (${ARCH}) …"
curl -fsSL \
  "https://api.adoptium.net/v3/binary/latest/21/ga/linux/${ARCH}/jre/hotspot/normal/eclipse?project=jdk" \
  -o "$OUT"
echo "Done: $(pwd)/$OUT ($(du -h "$OUT" | cut -f1))"
