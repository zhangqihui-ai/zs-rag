#!/usr/bin/env bash
# =============================================================================
# 将 docker-compose.prod.yml 用到的镜像推送到公司私有仓库（完全离线 prod 部署）
#
# 用法（能访问 Docker Hub / 外网 apt 的构建机）：
#
#   docker login 192.168.252.252:5566
#   VITE_API_BASE_URL=http://192.168.252.115:8091 ./scripts/push-images-to-registry.sh
#
# 内网 / 无法访问 deb.debian.org 的构建机（使用 Dockerfile.local + 私有仓库基础镜像）：
#
#   # 1) 在有网机器准备 offline_deps（仅需做一次，随仓库拷贝到内网）：
#   #    cd backend && ./scripts/download_offline_wheels.sh
#   #
#   # 2) 确保私有仓库已有 python:3.12-slim（可先单独 push 基础镜像，或从 Hub 镜像一次）
#   docker login 192.168.252.252:5566
#   VITE_API_BASE_URL=http://192.168.252.115:8091 ./scripts/push-images-to-registry.sh --offline
#
#   前端若无法 npm ci / 仓库无 node:20-alpine，可在有网机先构建 dist 再推送：
#   #   cd web && VITE_API_BASE_URL=http://192.168.252.115:8091 npm ci && npm run build:deploy
#   #   ./scripts/push-images-to-registry.sh --offline
#   #   （有 web/dist 时跳过 node 镜像，仅需 nginx:alpine；缺镜像用 scripts/sync-registry-image.sh 同步）
#
#   若启用 MinerU / ODL Hybrid：
#   ./scripts/push-images-to-registry.sh --mineru --odl-hybrid
#
#   推送 dev compose 镜像：
#   ./scripts/push-images-to-registry.sh --dev
#
# 可选环境变量：
#   REGISTRY=192.168.252.252:5566
#   IMAGE_NAMESPACE=zs-rag
#   VITE_API_BASE_URL=...              【prod 必设】前端 API 根地址
#   BACKEND_DOCKERFILE=Dockerfile        内网加 --offline 时自动为 Dockerfile.local
#   BASE_IMAGE=...                     默认 ${REGISTRY}/${IMAGE_NAMESPACE}/python:3.12-slim
#   NODE_IMAGE / NGINX_IMAGE           前端构建基础镜像（默认从私有仓库拉取）
#   APT_MIRROR=                        在线 Dockerfile 可用国内 Debian 源
#
# 可选参数：
#   --offline      内网离线构建：仅从私有仓库拉基础镜像，backend 用 Dockerfile.local
#   --dev          推送 dev compose 镜像
#   --mineru       推送 MinerU sidecar
#   --odl-hybrid   推送 python:3.12-slim（sidecar 用）
#   --skip-build   仅同步/推送第三方镜像，不构建前后端
# =============================================================================
set -euo pipefail

REGISTRY="${REGISTRY:-192.168.252.252:5566}"
IMAGE_NAMESPACE="${IMAGE_NAMESPACE:-zs-rag}"
BACKEND_DOCKERFILE="${BACKEND_DOCKERFILE:-Dockerfile}"
APT_MIRROR="${APT_MIRROR:-}"
VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://192.168.252.115:8091}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="prod"
OFFLINE=false
WITH_MINERU=false
WITH_ODL_HYBRID=false
SKIP_BUILD=false

for arg in "$@"; do
  case "$arg" in
    --dev) MODE="dev" ;;
    --offline) OFFLINE=true ;;
    --mineru) WITH_MINERU=true ;;
    --odl-hybrid) WITH_ODL_HYBRID=true ;;
    --skip-build) SKIP_BUILD=true ;;
    -h|--help)
      sed -n '1,45p' "$0"
      exit 0
      ;;
    *)
      echo "未知参数: $arg（可用 --offline --dev --mineru --odl-hybrid --skip-build）" >&2
      exit 1
      ;;
  esac
done

if [[ "$OFFLINE" == true && "$BACKEND_DOCKERFILE" == "Dockerfile" ]]; then
  BACKEND_DOCKERFILE="Dockerfile.local"
fi

BASE_IMAGE="${BASE_IMAGE:-$(printf '%s/%s/python:3.12-slim' "$REGISTRY" "$IMAGE_NAMESPACE")}"
NODE_IMAGE="${NODE_IMAGE:-$(printf '%s/%s/node:20-alpine' "$REGISTRY" "$IMAGE_NAMESPACE")}"
NGINX_IMAGE="${NGINX_IMAGE:-$(printf '%s/%s/nginx:alpine' "$REGISTRY" "$IMAGE_NAMESPACE")}"

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }

registry_tag() {
  echo "${REGISTRY}/${IMAGE_NAMESPACE}/$1"
}

mirror_pull_tag_push() {
  local src="$1"
  local dest_name="$2"
  local dst
  dst="$(registry_tag "$dest_name")"

  log "Pull  $src"
  docker pull "$src"
  log "Tag   $dst"
  docker tag "$src" "$dst"
  log "Push  $dst"
  docker push "$dst"
}

pull_registry_image() {
  local dest_name="$1"
  local dst
  dst="$(registry_tag "$dest_name")"
  log "Pull from registry: $dst"
  docker pull "$dst"
}

check_offline_backend_deps() {
  local has_wheel=false has_jre=false
  shopt -s nullglob
  local wheels=(backend/offline_deps/*.whl backend/offline_deps/*.tar.gz)
  shopt -u nullglob
  if ((${#wheels[@]} > 0)); then
    has_wheel=true
  fi
  shopt -s nullglob
  local jres=(backend/offline_deps/jre/*.tar.gz)
  shopt -u nullglob
  if ((${#jres[@]} > 0)); then
    has_jre=true
  fi

  if [[ "$has_wheel" != true ]]; then
    echo "错误: backend/offline_deps/ 下无 wheel/tar.gz。" >&2
    echo "  请在有网机器执行: cd backend && ./scripts/download_offline_wheels.sh" >&2
    echo "  再将 offline_deps/ 目录拷贝到内网构建机。" >&2
    exit 1
  fi
  if [[ "$has_jre" != true ]]; then
    echo "警告: 未找到 backend/offline_deps/jre/*.tar.gz，构建可能回退 apt 并失败。" >&2
    echo "  建议: cd backend && ./scripts/download_offline_jre.sh" >&2
  fi
}

log "Mode     : ${MODE}$( [[ "$OFFLINE" == true ]] && echo ' (offline)' )"
log "Registry : ${REGISTRY}"
log "Namespace: ${IMAGE_NAMESPACE}"
log "Backend  : ${BACKEND_DOCKERFILE}"
log "Project  : ${ROOT_DIR}"

if ! docker info >/dev/null 2>&1; then
  echo "错误: 无法连接 Docker daemon" >&2
  exit 1
fi

USE_FRONTEND_BUNDLE=false
if [[ "$MODE" == "prod" && -f web/dist/index.html ]]; then
  USE_FRONTEND_BUNDLE=true
  log "检测到 web/dist/，离线构建前端将跳过 node:20-alpine（使用 Dockerfile.prod-bundle）"
fi

if [[ "$MODE" == "prod" ]]; then
  # 目标机 compose 运行所需
  THIRD_PARTY_IMAGES=(
    "postgres:16-alpine|postgres:16-alpine"
    "quay.io/coreos/etcd:v3.5.18|etcd:v3.5.18"
    "minio/minio:RELEASE.2025-01-20T14-49-07Z|minio:RELEASE.2025-01-20T14-49-07Z"
    "milvusdb/milvus:v2.4.15|milvus:v2.4.15"
    "neo4j:5.26-community|neo4j:5.26-community"
    "opensearchproject/opensearch:3.6.0|opensearch:3.6.0"
  )
  # 仅在本机构建 backend/frontend 时需要
  if [[ "$SKIP_BUILD" == false ]]; then
    THIRD_PARTY_IMAGES+=("python:3.12-slim|python:3.12-slim")
    THIRD_PARTY_IMAGES+=("nginx:alpine|nginx:alpine")
    if [[ "$USE_FRONTEND_BUNDLE" != true ]]; then
      THIRD_PARTY_IMAGES+=("node:20-alpine|node:20-alpine")
    fi
  fi
else
  THIRD_PARTY_IMAGES=(
    "postgres:16|postgres:16"
    "quay.io/coreos/etcd:v3.5.5|etcd:v3.5.5"
    "minio/minio:RELEASE.2025-09-07T16-13-09Z|minio:RELEASE.2025-09-07T16-13-09Z"
    "milvusdb/milvus:v2.5.6|milvus:v2.5.6"
    "neo4j:5.26|neo4j:5.26"
    "opensearchproject/opensearch:3.6.0|opensearch:3.6.0"
    "node:20-alpine|node:20-alpine"
    "python:3.12-slim|python:3.12-slim"
  )
fi

if [[ "$WITH_ODL_HYBRID" == true && "$MODE" == "prod" ]]; then
  : # python:3.12-slim 已在 prod 列表
elif [[ "$WITH_ODL_HYBRID" == true ]]; then
  THIRD_PARTY_IMAGES+=("python:3.12-slim|python:3.12-slim")
fi

for entry in "${THIRD_PARTY_IMAGES[@]}"; do
  src="${entry%%|*}"
  dest="${entry##*|}"
  if [[ "$OFFLINE" == true ]]; then
    if ! pull_registry_image "$dest"; then
      echo "错误: 私有仓库缺少镜像 $(registry_tag "$dest")" >&2
      echo "  在有外网的机器执行以下命令同步后重试：" >&2
      echo "    docker login ${REGISTRY}" >&2
      echo "    ./scripts/sync-registry-image.sh ${src} ${dest}" >&2
      echo "  或一次性同步全部基础镜像：" >&2
      echo "    ./scripts/push-images-to-registry.sh --skip-build" >&2
      exit 1
    fi
  else
    mirror_pull_tag_push "$src" "$dest"
  fi
done

if [[ "$SKIP_BUILD" == false ]]; then
  build_args=()
  if [[ -n "$APT_MIRROR" ]]; then
    build_args+=(--build-arg "APT_MIRROR=${APT_MIRROR}")
  fi

  if [[ "$OFFLINE" == true || "$BACKEND_DOCKERFILE" == "Dockerfile.local" ]]; then
    check_offline_backend_deps
    build_args+=(--build-arg "BASE_IMAGE=${BASE_IMAGE}")
    log "Backend base image: ${BASE_IMAGE}"
  fi

  if [[ "$MODE" == "prod" ]]; then
    BACKEND_DST="$(registry_tag "backend:prod")"
    FRONTEND_DST="$(registry_tag "frontend:prod")"

    log "Build backend:prod (${BACKEND_DOCKERFILE}, target=production)"
    docker build \
      "${build_args[@]}" \
      -f "backend/${BACKEND_DOCKERFILE}" \
      --target production \
      -t "$BACKEND_DST" \
      ./backend
    log "Push  $BACKEND_DST"
    docker push "$BACKEND_DST"

    if [[ -f web/dist/index.html ]]; then
      log "Build frontend:prod (Dockerfile.prod-bundle, 使用已有 web/dist/)"
      docker build \
        --build-arg "NGINX_IMAGE=${NGINX_IMAGE}" \
        -f web/Dockerfile.prod-bundle \
        -t "$FRONTEND_DST" \
        ./web
    else
      log "Build frontend:prod (Dockerfile, VITE_API_BASE_URL=${VITE_API_BASE_URL})"
      log "  提示: 内网若 npm ci 失败，请先在 web/ 目录执行 npm ci && npm run build 后重试 --offline"
      docker build \
        --build-arg "VITE_API_BASE_URL=${VITE_API_BASE_URL}" \
        --build-arg "NODE_IMAGE=${NODE_IMAGE}" \
        --build-arg "NGINX_IMAGE=${NGINX_IMAGE}" \
        -f web/Dockerfile \
        --target production \
        -t "$FRONTEND_DST" \
        ./web
    fi
    log "Push  $FRONTEND_DST"
    docker push "$FRONTEND_DST"
  else
    BACKEND_DST="$(registry_tag "backend:dev")"
    log "Build backend:dev (${BACKEND_DOCKERFILE}, target=development)"
    docker build \
      "${build_args[@]}" \
      -f "backend/${BACKEND_DOCKERFILE}" \
      --target development \
      -t "$BACKEND_DST" \
      ./backend
    log "Push  $BACKEND_DST"
    docker push "$BACKEND_DST"
  fi

  if [[ "$WITH_MINERU" == true ]]; then
    MINERU_DST="$(registry_tag "mineru:cpu")"
    log "Build mineru:cpu (Dockerfile.mineru-cpu)"
    docker build \
      -f backend/Dockerfile.mineru-cpu \
      -t "$MINERU_DST" \
      ./backend
    log "Push  $MINERU_DST"
    docker push "$MINERU_DST"
  fi
else
  log "跳过自建镜像构建（--skip-build）"
fi

if [[ "$MODE" == "prod" ]]; then
  COMPOSE_FILES="-f docker-compose.prod.yml -f docker-compose.prod.registry.yml"
else
  COMPOSE_FILES="-f docker-compose.yml -f docker-compose.registry.yml"
fi

cat <<EOF

================================================================================
推送完成（${MODE}$( [[ "$OFFLINE" == true ]] && echo ', offline build' )）。

【prod 目标机 192.168.252.115】
  docker compose ${COMPOSE_FILES} pull
  docker compose ${COMPOSE_FILES} up -d --no-build
  docker compose ${COMPOSE_FILES} exec backend python -m alembic upgrade head

  前端: http://192.168.252.115:8090
  后端: http://192.168.252.115:8091/docs
  前端 API 构建地址: ${VITE_API_BASE_URL}
================================================================================
EOF
