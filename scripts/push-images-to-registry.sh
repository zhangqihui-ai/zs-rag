#!/usr/bin/env bash
# =============================================================================
# 将 docker-compose.prod.yml 用到的镜像推送到公司私有仓库（完全离线 prod 部署）
#
# 用法（在有外网 / 能 docker pull & docker build 的机器上执行）：
#
#   docker login 192.168.252.252:5566
#
#   # 按目标机 IP/端口构建前端 API 地址并推送全部镜像（默认 prod）
#   VITE_API_BASE_URL=http://192.168.252.115:8091 ./scripts/push-images-to-registry.sh
#
#   若启用 MinerU / ODL Hybrid（dev compose 可选 sidecar，prod 暂未编排）：
#   ./scripts/push-images-to-registry.sh --mineru --odl-hybrid
#
#   推送 dev compose 镜像（挂载源码的开发模式，一般不用于完全离线）：
#   ./scripts/push-images-to-registry.sh --dev
#
# 可选环境变量：
#   REGISTRY=192.168.252.252:5566      私有仓库地址
#   IMAGE_NAMESPACE=zs-rag               仓库内项目命名空间
#   VITE_API_BASE_URL=...              【prod 必设】前端构建时写入的 API 根地址
#   BACKEND_DOCKERFILE=Dockerfile        离线构建 backend 可改为 Dockerfile.local
#   APT_MIRROR=                          传给 backend 构建（国内 Debian 镜像）
#
# 可选参数：
#   --dev          推送 docker-compose.yml（dev）镜像，而非 prod
#   --mineru       同时构建并推送 MinerU sidecar 镜像
#   --odl-hybrid   同时推送 OpenDataLoader Hybrid 用的 python:3.12-slim
#   --skip-build   仅推送第三方基础镜像，不构建 backend / frontend / mineru
#
# 目标机（192.168.252.115）部署步骤见脚本末尾输出。
# =============================================================================
set -euo pipefail

REGISTRY="${REGISTRY:-192.168.252.252:5566}"
IMAGE_NAMESPACE="${IMAGE_NAMESPACE:-zs-rag}"
BACKEND_DOCKERFILE="${BACKEND_DOCKERFILE:-Dockerfile}"
APT_MIRROR="${APT_MIRROR:-}"
# prod 前端构建：浏览器直连 backend 宿主机端口（与 .env.deploy.example 默认一致）
VITE_API_BASE_URL="${VITE_API_BASE_URL:-http://192.168.252.115:8091}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="prod"
WITH_MINERU=false
WITH_ODL_HYBRID=false
SKIP_BUILD=false

for arg in "$@"; do
  case "$arg" in
    --dev) MODE="dev" ;;
    --mineru) WITH_MINERU=true ;;
    --odl-hybrid) WITH_ODL_HYBRID=true ;;
    --skip-build) SKIP_BUILD=true ;;
    -h|--help)
      sed -n '1,35p' "$0"
      exit 0
      ;;
    *)
      echo "未知参数: $arg（可用 --dev --mineru --odl-hybrid --skip-build）" >&2
      exit 1
      ;;
  esac
done

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
  echo "$dst"
}

log "Mode     : ${MODE}"
log "Registry : ${REGISTRY}"
log "Namespace: ${IMAGE_NAMESPACE}"
log "Project  : ${ROOT_DIR}"

if ! docker info >/dev/null 2>&1; then
  echo "错误: 无法连接 Docker daemon" >&2
  exit 1
fi

if [[ "$MODE" == "prod" ]]; then
  THIRD_PARTY_IMAGES=(
    "postgres:16-alpine|postgres:16-alpine"
    "quay.io/coreos/etcd:v3.5.18|etcd:v3.5.18"
    "minio/minio:RELEASE.2025-01-20T14-49-07Z|minio:RELEASE.2025-01-20T14-49-07Z"
    "milvusdb/milvus:v2.4.15|milvus:v2.4.15"
    "neo4j:5.26-community|neo4j:5.26-community"
    "opensearchproject/opensearch:3.6.0|opensearch:3.6.0"
  )
else
  THIRD_PARTY_IMAGES=(
    "postgres:16|postgres:16"
    "quay.io/coreos/etcd:v3.5.5|etcd:v3.5.5"
    "minio/minio:RELEASE.2025-09-07T16-13-09Z|minio:RELEASE.2025-09-07T16-13-09Z"
    "milvusdb/milvus:v2.5.6|milvus:v2.5.6"
    "neo4j:5.26|neo4j:5.26"
    "opensearchproject/opensearch:3.6.0|opensearch:3.6.0"
    "node:20-alpine|node:20-alpine"
  )
fi

if [[ "$WITH_ODL_HYBRID" == true ]]; then
  THIRD_PARTY_IMAGES+=("python:3.12-slim|python:3.12-slim")
fi

for entry in "${THIRD_PARTY_IMAGES[@]}"; do
  src="${entry%%|*}"
  dest="${entry##*|}"
  mirror_pull_tag_push "$src" "$dest"
done

if [[ "$SKIP_BUILD" == false ]]; then
  build_args=()
  if [[ -n "$APT_MIRROR" ]]; then
    build_args+=(--build-arg "APT_MIRROR=${APT_MIRROR}")
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

    log "Build frontend:prod (VITE_API_BASE_URL=${VITE_API_BASE_URL})"
    docker build \
      --build-arg "VITE_API_BASE_URL=${VITE_API_BASE_URL}" \
      -f web/Dockerfile \
      --target production \
      -t "$FRONTEND_DST" \
      ./web
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
推送完成（${MODE}）。私有仓库 ${REGISTRY}/${IMAGE_NAMESPACE}/ 下应有对应镜像。

【prod 完全离线目标机 192.168.252.115 部署 checklist】

1) 配置 Docker 信任 HTTP 私有仓库（若仓库非 HTTPS）：
   /etc/docker/daemon.json 增加：
   {
     "insecure-registries": ["${REGISTRY}"]
   }
   然后 systemctl restart docker

2) 准备部署目录（无需 git 源码，只需 3 个文件）：
   mkdir -p ~/zs-rag-deploy && cd ~/zs-rag-deploy
   # 从有网机器拷贝：
   #   docker-compose.prod.yml
   #   docker-compose.prod.registry.yml
   #   .env.deploy.example  -> 复制为 .env 并修改密码

   docker login ${REGISTRY}

3) 编辑 .env（必改项）：
   REGISTRY=${REGISTRY}
   IMAGE_NAMESPACE=${IMAGE_NAMESPACE}
   FRONTEND_PORT=8090
   BACKEND_PORT=8091
   CORS_ORIGINS=http://192.168.252.115:8090
   POSTGRES_PASSWORD / JWT_SECRET / ADMIN_PASSWORD / NEO4J_PASSWORD / MINIO_ROOT_PASSWORD

   注意：VITE_API_BASE_URL 已在推送时写入前端镜像（当前为 ${VITE_API_BASE_URL}）。
   若目标机 IP/端口不同，请用正确的 VITE_API_BASE_URL 重新执行本推送脚本。

4) 拉取镜像并启动（不本地 build）：
   docker compose ${COMPOSE_FILES} pull
   docker compose ${COMPOSE_FILES} up -d --no-build

5) 首次启动后跑数据库迁移：
   docker compose ${COMPOSE_FILES} exec backend python -m alembic upgrade head

【访问地址】
  前端：http://192.168.252.115:8090
  后端：http://192.168.252.115:8091/docs

【防火墙】
  仅需开放 FRONTEND_PORT、BACKEND_PORT；中间件端口均在 Docker 内网，无需对外暴露。

【与 dev 的区别】
  prod 镜像内已包含前后端代码与依赖，目标机不需要 ./backend、./web 源码目录，也不跑 npm ci。
================================================================================
EOF
