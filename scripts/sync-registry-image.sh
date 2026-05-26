#!/usr/bin/env bash
# 将单个 Docker Hub 镜像同步到私有仓库（在有外网的机器上执行）
#
# 用法：
#   docker login 192.168.252.252:5566
#   ./scripts/sync-registry-image.sh node:20-alpine
#   ./scripts/sync-registry-image.sh nginx:alpine
#   ./scripts/sync-registry-image.sh docker.io/library/python:3.12-slim python:3.12-slim
#
# 环境变量：REGISTRY、IMAGE_NAMESPACE（同 push-images-to-registry.sh）
set -euo pipefail

REGISTRY="${REGISTRY:-192.168.252.252:5566}"
IMAGE_NAMESPACE="${IMAGE_NAMESPACE:-zs-rag}"

if [[ $# -lt 1 ]]; then
  echo "用法: $0 <hub镜像> [仓库内名称:tag]" >&2
  echo "示例: $0 node:20-alpine" >&2
  exit 1
fi

SRC="$1"
DEST_NAME="${2:-$1}"
# 无 registry 前缀时补 docker.io/library/
if [[ "$SRC" != */* ]]; then
  SRC="docker.io/library/${SRC}"
elif [[ "$SRC" != *.*/* ]]; then
  SRC="docker.io/${SRC}"
fi

DEST="${REGISTRY}/${IMAGE_NAMESPACE}/${DEST_NAME}"

echo "Pull  ${SRC}"
docker pull "${SRC}"
echo "Tag   ${DEST}"
docker tag "${SRC}" "${DEST}"
echo "Push  ${DEST}"
docker push "${DEST}"
echo "完成: ${DEST}"
