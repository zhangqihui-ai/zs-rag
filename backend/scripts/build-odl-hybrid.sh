#!/usr/bin/env bash
# 构建 odl-hybrid 镜像，尽量复用 Docker 层缓存。
#
# 用法（在项目根目录或 backend/ 下均可）：
#   ./backend/scripts/build-odl-hybrid.sh
#   ./backend/scripts/build-odl-hybrid.sh --rebuild-base   # 强制重做 apt+pip（慢）
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
cd "${ROOT}"

IMAGE="${ODL_HYBRID_IMAGE:-zs-rag-odl-hybrid:latest}"
BASE_TAG="${ODL_HYBRID_BASE_IMAGE:-zs-rag-odl-hybrid:base}"
REBUILD_BASE=false

for arg in "$@"; do
  case "${arg}" in
    --rebuild-base) REBUILD_BASE=true ;;
    -h|--help)
      echo "Usage: $0 [--rebuild-base]"
      exit 0
      ;;
    *) echo "Unknown option: ${arg}" >&2; exit 1 ;;
  esac
done

export DOCKER_BUILDKIT=1

cache_args=(--cache-from "${BASE_TAG}" --cache-from "${IMAGE}")

if [[ "${REBUILD_BASE}" == true ]]; then
  echo "==> rebuild base (apt + pip, 较慢) -> ${BASE_TAG}"
  docker build "${cache_args[@]}" --no-cache-filter base --target base \
    -f Dockerfile.odl-hybrid -t "${BASE_TAG}" .
else
  echo "==> ensure base layer cached -> ${BASE_TAG}"
  docker build "${cache_args[@]}" --target base \
    -f Dockerfile.odl-hybrid -t "${BASE_TAG}" .
fi

echo "==> build runtime (模型层；base 命中缓存时通常 ~1 分钟) -> ${IMAGE}"
docker build "${cache_args[@]}" --target runtime \
  -f Dockerfile.odl-hybrid -t "${IMAGE}" .

echo "Done: ${IMAGE}"
docker images "${IMAGE%%:*}" --format 'table {{.Repository}}\t{{.Tag}}\t{{.Size}}'
