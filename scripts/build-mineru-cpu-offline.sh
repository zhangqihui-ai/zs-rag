#!/usr/bin/env bash
# 在已有 mineru:cpu 镜像上快速叠加模型，打出 mineru:cpu-offline 并可选推送私有仓库。
#
# 用法：
#   ./scripts/export-mineru-models-bundle.sh zs-rag-mineru
#   ./scripts/build-mineru-cpu-offline.sh
#   ./scripts/build-mineru-cpu-offline.sh --push
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

REGISTRY="${REGISTRY:-192.168.252.252:5566}"
IMAGE_NAMESPACE="${IMAGE_NAMESPACE:-zs-rag}"
MINERU_CPU_IMAGE="${MINERU_CPU_IMAGE:-${REGISTRY}/${IMAGE_NAMESPACE}/mineru:cpu}"
OFFLINE_TAG="${MINERU_CPU_OFFLINE_TAG:-mineru:cpu-offline}"
DO_PUSH=false
DOCKERIGNORE_BAK=""

for arg in "$@"; do
  case "$arg" in
    --push) DO_PUSH=true ;;
    -h|--help)
      sed -n '1,12p' "$0"
      exit 0
      ;;
    *) echo "未知参数: $arg（支持 --push）" >&2; exit 1 ;;
  esac
done

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }

restore_dockerignore() {
  if [[ -n "$DOCKERIGNORE_BAK" && -f "$DOCKERIGNORE_BAK" ]]; then
    mv -f "$DOCKERIGNORE_BAK" backend/.dockerignore
    DOCKERIGNORE_BAK=""
  fi
}
trap restore_dockerignore EXIT

if [[ ! -d backend/mineru_models_bundle ]] || [[ -z "$(find backend/mineru_models_bundle -type f 2>/dev/null | head -1)" ]]; then
  echo "错误: backend/mineru_models_bundle/ 为空。" >&2
  echo "  请先: ./scripts/export-mineru-models-bundle.sh [容器名]" >&2
  exit 1
fi

# backend/.dockerignore 默认排除 mineru_models_bundle/，构建离线镜像时临时放开
DOCKERIGNORE_BAK="backend/.dockerignore.mineru-build.bak"
cp backend/.dockerignore "$DOCKERIGNORE_BAK"
grep -v '^mineru_models_bundle/$' "$DOCKERIGNORE_BAK" > backend/.dockerignore

LOCAL_TAG="zs-rag-mineru:cpu-offline"
REMOTE_TAG="${REGISTRY}/${IMAGE_NAMESPACE}/${OFFLINE_TAG}"

log "FROM   ${MINERU_CPU_IMAGE}"
log "BUILD  -> ${LOCAL_TAG}"
log "REMOTE -> ${REMOTE_TAG}"

docker pull "${MINERU_CPU_IMAGE}" 2>/dev/null || true

DOCKER_BUILDKIT=1 docker build \
  -f backend/Dockerfile.mineru-cpu-offline \
  --build-arg "MINERU_CPU_IMAGE=${MINERU_CPU_IMAGE}" \
  -t "${LOCAL_TAG}" \
  ./backend

restore_dockerignore
trap - EXIT

docker tag "${LOCAL_TAG}" "${REMOTE_TAG}"

if [[ "$DO_PUSH" == true ]]; then
  log "Push ${REMOTE_TAG}"
  docker push "${REMOTE_TAG}"
fi

cat <<EOF

完成。离线 prod 建议在 .env 设置：
  MINERU_CPU_IMAGE=${REMOTE_TAG}
  MINERU_MODEL_SOURCE=local
  MINERU_BASE_URL=http://mineru:8000

勿对 mineru 服务挂载空的 mineru_models 卷（会盖住镜像内 /models）。
EOF
