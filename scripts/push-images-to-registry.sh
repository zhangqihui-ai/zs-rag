#!/usr/bin/env bash
# =============================================================================
# 将 docker-compose.prod.yml 用到的镜像推送到公司私有仓库（完全离线 prod 部署）
#
# ─────────────────────────────────────────────────────────────────────────────
# 【代码变更后发布流程】prod 镜像内已打包代码，改代码后必须重新构建并推送
# ─────────────────────────────────────────────────────────────────────────────
#
# 构建机（有仓库源码，能 docker build / 访问私有仓库 192.168.252.252:5566）：
#
#   docker login 192.168.252.252:5566
#
#   # ① 只改了 backend（Python / API / 迁移等）
#   ./scripts/push-images-to-registry.sh --offline --backend-only
#
#   # ② 只改了 web 前端（Vue/TS/样式等）
#   #    须先重新生成 dist，再只构建/推送 frontend（不会 rebuild backend）
#   cd web && npm ci && npm run build:deploy
#   ./scripts/push-images-to-registry.sh --offline --frontend-only
#
#   # ③ 前后端都改了（默认 = 推送 backend + frontend，不碰 MinerU）：
#   cd web && npm ci && npm run build:deploy
#   ./scripts/push-images-to-registry.sh --offline
#
#   # ④ 全量含 MinerU CPU sidecar：
#   ./scripts/push-images-to-registry.sh --offline --with-mineru
#
#   # ④' 全量含 MinerU GPU（需能拉 vllm/vllm-openai 或已同步到私有仓库）：
#   ./scripts/push-images-to-registry.sh --offline --with-mineru-gpu
#
#   # ⑤ 只推送 MinerU CPU / GPU（不构建前后端）：
#   ./scripts/push-images-to-registry.sh --offline --mineru-only
#   ./scripts/push-images-to-registry.sh --offline --mineru-offline-only   # 在已有 mineru:cpu 上叠模型，快
#   ./scripts/push-images-to-registry.sh --offline --mineru-gpu-only
#
#   # 仅改了 .env / CORS / 端口、未改代码：目标机改 .env 后 force-recreate 即可，不必跑本脚本
#
# 目标机 192.168.252.115（只需 compose + .env，无需源码）：
#
#   docker login 192.168.252.252:5566
#   docker compose -f docker-compose.prod.yml -f docker-compose.prod.registry.yml pull
#   docker compose -f docker-compose.prod.yml -f docker-compose.prod.registry.yml up -d --no-build
#
#  若只更新了 前端 镜像，可只重建 frontend
#   docker compose -f docker-compose.prod.yml -f docker-compose.prod.registry.yml pull frontend
#   docker compose -f docker-compose.prod.yml -f docker-compose.prod.registry.yml up -d --no-build --force-recreate frontend

#   # 若只更新了 backend 镜像，可只重建 backend：
#   docker compose -f docker-compose.prod.yml -f docker-compose.prod.registry.yml up -d --no-build --force-recreate backend
#   docker compose -f docker-compose.prod.yml -f docker-compose.prod.registry.yml up -d --no-build --force-recreate frontend
#    启动miner u
#   docker compose -f docker-compose.prod.yml -f docker-compose.prod.registry.yml pull mineru

#   docker compose -f docker-compose.prod.yml -f docker-compose.prod.registry.yml --profile mineru up -d --no-build --force-recreate mineru-cpu
#   docker compose -f docker-compose.prod.yml -f docker-compose.prod.registry.yml up -d --no-build --force-recreate backend

#   # 后端有数据库迁移时（alembic 新版本）：
#   docker compose -f docker-compose.prod.yml -f docker-compose.prod.registry.yml exec backend python -m alembic upgrade head
#
# ─────────────────────────────────────────────────────────────────────────────
# 首次 / 内网离线环境准备
# ─────────────────────────────────────────────────────────────────────────────
#
#   # offline_deps（仅需做一次，拷到内网构建机 backend/offline_deps/）：
#   cd backend && ./scripts/download_offline_wheels.sh
#
#   # 内网构建并推送（--offline：Dockerfile.local + 私有仓库 python/nginx 等）：
#   docker login 192.168.252.252:5566
#   cd web && npm run build:deploy
#   ./scripts/push-images-to-registry.sh --offline
#
#   缺单个基础镜像：./scripts/sync-registry-image.sh node:20-alpine
#
#   仅推送 MinerU CPU/GPU：--mineru-only / --mineru-gpu-only
#   全量含 MinerU CPU/GPU：--with-mineru / --with-mineru-gpu
#   GPU 离线基础镜像：./scripts/sync-registry-image.sh vllm/vllm-openai:v0.11.2
#     并 tag 为 ${REGISTRY}/${IMAGE_NAMESPACE}/vllm-openai:v0.11.2，构建时设 MINERU_VLLM_BASE_IMAGE
#
#   推送 dev compose 镜像（挂载源码，非 prod 离线）：
#   ./scripts/push-images-to-registry.sh --dev
#
# 可选环境变量：
#   REGISTRY=192.168.252.252:5566
#   IMAGE_NAMESPACE=zs-rag
#   VITE_API_BASE_URL=...              【prod 推荐留空：同源 + nginx 反代 backend】
#   BACKEND_DOCKERFILE=Dockerfile      内网 --offline 时自动为 Dockerfile.local
#   BASE_IMAGE / NODE_IMAGE / NGINX_IMAGE
#   APT_MIRROR=                        在线 Dockerfile 可用国内 Debian 源
#
# 可选参数：
#   --offline        内网离线构建
#   --dev            推送 dev compose 镜像
#   （默认）         构建并推送 backend:prod + frontend:prod
#   --with-mineru       额外构建并推送 mineru:cpu
#   --with-mineru-gpu   额外构建并推送 mineru:gpu（Dockerfile.mineru-gpu）
#   --frontend-only     仅 frontend:prod
#   --backend-only      仅 backend:prod
#   --mineru-only       仅 mineru:cpu（不构建前后端）
#   --mineru-gpu-only   仅 mineru:gpu
#   MINERU_VLLM_BASE_IMAGE  GPU 构建的 FROM（默认 vllm/vllm-openai:v0.11.2）
#   --odl-hybrid     同时推送 python:3.12-slim（ODL Hybrid sidecar，可选）
#   --skip-build     仅同步中间件等第三方镜像，不构建自建镜像
# =============================================================================
set -euo pipefail

REGISTRY="${REGISTRY:-192.168.252.252:5566}"
IMAGE_NAMESPACE="${IMAGE_NAMESPACE:-zs-rag}"
BACKEND_DOCKERFILE="${BACKEND_DOCKERFILE:-Dockerfile}"
APT_MIRROR="${APT_MIRROR:-}"
# 空字符串 = 同源 nginx 反代（prod 推荐）；显式设置则浏览器直连该后端地址
VITE_API_BASE_URL="${VITE_API_BASE_URL:-}"

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT_DIR"

MODE="prod"
OFFLINE=false
BUILD_MINERU_CPU=false
BUILD_MINERU_CPU_OFFLINE=false
BUILD_MINERU_GPU=false
WITH_ODL_HYBRID=false
SKIP_BUILD=false
BUILD_BACKEND=true
BUILD_FRONTEND=true

for arg in "$@"; do
  case "$arg" in
    --dev) MODE="dev" ;;
    --offline) OFFLINE=true ;;
    --with-mineru) BUILD_MINERU_CPU=true ;;
    --with-mineru-gpu) BUILD_MINERU_GPU=true ;;
    --mineru-only|--mineru)
      BUILD_BACKEND=false
      BUILD_FRONTEND=false
      BUILD_MINERU_CPU=true
      ;;
    --mineru-gpu-only)
      BUILD_BACKEND=false
      BUILD_FRONTEND=false
      BUILD_MINERU_GPU=true
      ;;
    --mineru-offline-only)
      BUILD_BACKEND=false
      BUILD_FRONTEND=false
      BUILD_MINERU_CPU_OFFLINE=true
      ;;
    --odl-hybrid) WITH_ODL_HYBRID=true ;;
    --skip-build) SKIP_BUILD=true ;;
    --frontend-only) BUILD_BACKEND=false; BUILD_FRONTEND=true ;;
    --backend-only) BUILD_BACKEND=true; BUILD_FRONTEND=false ;;
    -h|--help)
      sed -n '1,85p' "$0"
      exit 0
      ;;
    *)
      echo "未知参数: $arg" >&2
      echo "  常用: --offline [--frontend-only|--backend-only|--mineru-only|--mineru-offline-only|--mineru-gpu-only]" >&2
      exit 1
      ;;
  esac
done

exclusive=0
[[ "$BUILD_BACKEND" == false && "$BUILD_FRONTEND" == true ]] && exclusive=$((exclusive + 1))
[[ "$BUILD_BACKEND" == true && "$BUILD_FRONTEND" == false ]] && exclusive=$((exclusive + 1))
[[ "$BUILD_BACKEND" == false && "$BUILD_FRONTEND" == false && "$BUILD_MINERU_CPU" == true && "$BUILD_MINERU_GPU" == false && "$SKIP_BUILD" == false ]] && exclusive=$((exclusive + 1))
[[ "$BUILD_BACKEND" == false && "$BUILD_FRONTEND" == false && "$BUILD_MINERU_GPU" == true && "$BUILD_MINERU_CPU" == false && "$BUILD_MINERU_CPU_OFFLINE" == false && "$SKIP_BUILD" == false ]] && exclusive=$((exclusive + 1))
[[ "$BUILD_BACKEND" == false && "$BUILD_FRONTEND" == false && "$BUILD_MINERU_CPU_OFFLINE" == true && "$BUILD_MINERU_CPU" == false && "$BUILD_MINERU_GPU" == false && "$SKIP_BUILD" == false ]] && exclusive=$((exclusive + 1))
if [[ "$BUILD_BACKEND" == false && "$BUILD_FRONTEND" == false && ( "$BUILD_MINERU_CPU" == true || "$BUILD_MINERU_GPU" == true || "$BUILD_MINERU_CPU_OFFLINE" == true ) && "$SKIP_BUILD" == false ]]; then
  mcnt=0
  [[ "$BUILD_MINERU_CPU" == true ]] && mcnt=$((mcnt + 1))
  [[ "$BUILD_MINERU_GPU" == true ]] && mcnt=$((mcnt + 1))
  [[ "$BUILD_MINERU_CPU_OFFLINE" == true ]] && mcnt=$((mcnt + 1))
  if [[ "$mcnt" -gt 1 ]]; then
    echo "错误: --mineru-only、--mineru-offline-only、--mineru-gpu-only 只能三选一" >&2
    exit 1
  fi
fi
if [[ "$exclusive" -gt 1 ]]; then
  echo "错误: --frontend-only、--backend-only、--mineru-only、--mineru-offline-only、--mineru-gpu-only 只能五选一" >&2
  exit 1
fi
if [[ "$BUILD_BACKEND" == false && "$BUILD_FRONTEND" == false && ( "$BUILD_MINERU_CPU" == true || "$BUILD_MINERU_GPU" == true || "$BUILD_MINERU_CPU_OFFLINE" == true ) && "$SKIP_BUILD" == false ]]; then
  : # mineru-*-only
elif [[ ( "$BUILD_MINERU_CPU" == true || "$BUILD_MINERU_GPU" == true || "$BUILD_MINERU_CPU_OFFLINE" == true ) && "$exclusive" -eq 1 ]]; then
  echo "错误: --with-mineru* 不能与 --*-only 同时使用；仅推 MinerU 请用 --mineru-only 或 --mineru-gpu-only" >&2
  exit 1
fi

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
log "Build    : backend=${BUILD_BACKEND} frontend=${BUILD_FRONTEND} mineru_cpu=${BUILD_MINERU_CPU} mineru_offline=${BUILD_MINERU_CPU_OFFLINE} mineru_gpu=${BUILD_MINERU_GPU}"
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
  THIRD_PARTY_IMAGES=()
  # 目标机 compose 运行所需（--frontend-only / --backend-only 时不重复拉中间件）
  if [[ "$BUILD_BACKEND" == true && "$BUILD_FRONTEND" == true ]]; then
    THIRD_PARTY_IMAGES=(
      "postgres:16-alpine|postgres:16-alpine"
      "quay.io/coreos/etcd:v3.5.18|etcd:v3.5.18"
      "minio/minio:RELEASE.2025-01-20T14-49-07Z|minio:RELEASE.2025-01-20T14-49-07Z"
      "milvusdb/milvus:v2.4.15|milvus:v2.4.15"
      "neo4j:5.26-community|neo4j:5.26-community"
      "opensearchproject/opensearch:3.6.0|opensearch:3.6.0"
    )
  fi
  # 仅在本机构建 backend/frontend 时需要
  if [[ "$SKIP_BUILD" == false ]]; then
    if [[ "$BUILD_BACKEND" == true ]]; then
      THIRD_PARTY_IMAGES+=("python:3.12-slim|python:3.12-slim")
    fi
    if [[ "$BUILD_FRONTEND" == true ]]; then
      THIRD_PARTY_IMAGES+=("nginx:alpine|nginx:alpine")
      if [[ "$USE_FRONTEND_BUNDLE" != true ]]; then
        THIRD_PARTY_IMAGES+=("node:20-alpine|node:20-alpine")
      fi
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

  if [[ "$BUILD_BACKEND" == true && ( "$OFFLINE" == true || "$BACKEND_DOCKERFILE" == "Dockerfile.local" ) ]]; then
    check_offline_backend_deps
    build_args+=(--build-arg "BASE_IMAGE=${BASE_IMAGE}")
    log "Backend base image: ${BASE_IMAGE}"
  fi

  if [[ "$MODE" == "prod" ]]; then
    if [[ "$BUILD_BACKEND" == true ]]; then
      BACKEND_DST="$(registry_tag "backend:prod")"
      log "Build backend:prod (${BACKEND_DOCKERFILE}, target=production)"
      _backend_cache=()
      if docker pull "$BACKEND_DST" >/dev/null 2>&1; then
        _backend_cache=(--cache-from "$BACKEND_DST")
        log "Build cache: ${BACKEND_DST}"
      fi
      DOCKER_BUILDKIT=1 docker build \
        "${_backend_cache[@]}" \
        "${build_args[@]}" \
        -f "backend/${BACKEND_DOCKERFILE}" \
        --target production \
        -t "$BACKEND_DST" \
        ./backend
      log "Push  $BACKEND_DST"
      docker push "$BACKEND_DST"
    else
      log "跳过 backend:prod 构建（--frontend-only）"
    fi

    if [[ "$BUILD_FRONTEND" == true ]]; then
      FRONTEND_DST="$(registry_tag "frontend:prod")"
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
      log "跳过 frontend:prod 构建（--backend-only）"
    fi
  else
    if [[ "$BUILD_BACKEND" == true ]]; then
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
    if [[ "$BUILD_FRONTEND" == true ]]; then
      echo "错误: dev 模式请使用默认脚本推送 backend:dev；--frontend-only 仅用于 prod" >&2
      exit 1
    fi
  fi

  if [[ "$BUILD_MINERU_CPU" == true ]]; then
    MINERU_CPU_DST="$(registry_tag "mineru:cpu")"
    log "Build mineru:cpu (Dockerfile.mineru-cpu)"
    docker build \
      -f backend/Dockerfile.mineru-cpu \
      -t "$MINERU_CPU_DST" \
      ./backend
    log "Push  $MINERU_CPU_DST"
    docker push "$MINERU_CPU_DST"
  fi
  if [[ "$BUILD_MINERU_CPU_OFFLINE" == true ]]; then
    log "Build mineru:cpu-offline (Dockerfile.mineru-cpu-offline, FROM 已有 mineru:cpu)"
    "${ROOT_DIR}/scripts/build-mineru-cpu-offline.sh" --push
  fi
  if [[ "$BUILD_MINERU_GPU" == true ]]; then
    MINERU_GPU_DST="$(registry_tag "mineru:gpu")"
    VLLM_BASE_IMAGE="${MINERU_VLLM_BASE_IMAGE:-vllm/vllm-openai:v0.11.2}"
    log "Build mineru:gpu (Dockerfile.mineru-gpu, FROM=${VLLM_BASE_IMAGE})"
    _gpu_build_args=(
      -f backend/Dockerfile.mineru-gpu
      --build-arg "VLLM_BASE_IMAGE=${VLLM_BASE_IMAGE}"
      --build-arg "APT_MIRROR=${APT_MIRROR:-mirrors.aliyun.com}"
    )
    if [[ -n "${MINERU_GPU_SKIP_APT:-}" ]]; then
      _gpu_build_args+=(--build-arg "SKIP_APT_PACKAGES=${MINERU_GPU_SKIP_APT}")
    fi
    docker build \
      "${_gpu_build_args[@]}" \
      -t "$MINERU_GPU_DST" \
      ./backend
    log "Push  $MINERU_GPU_DST"
    docker push "$MINERU_GPU_DST"
  fi
else
  log "跳过自建镜像构建（--skip-build）"
fi

if [[ "$MODE" == "prod" ]]; then
  COMPOSE_FILES="-f docker-compose.prod.yml -f docker-compose.prod.registry.yml"
else
  COMPOSE_FILES="-f docker-compose.yml -f docker-compose.registry.yml"
fi

DEPLOY_HINT=""
if [[ "$MODE" == "prod" ]]; then
  if [[ "$BUILD_FRONTEND" == true && "$BUILD_BACKEND" == false ]]; then
    DEPLOY_HINT="  # 本次仅更新了 frontend:prod
  docker compose ${COMPOSE_FILES} pull frontend
  docker compose ${COMPOSE_FILES} up -d --no-build --force-recreate frontend"
  elif [[ "$BUILD_BACKEND" == true && "$BUILD_FRONTEND" == false ]]; then
    DEPLOY_HINT="  # 本次仅更新了 backend:prod
  docker compose ${COMPOSE_FILES} pull backend
  docker compose ${COMPOSE_FILES} up -d --no-build --force-recreate backend
  # 若镜像内含新 alembic 迁移：
  docker compose ${COMPOSE_FILES} exec backend python -m alembic upgrade head"
  elif [[ "$BUILD_BACKEND" == false && "$BUILD_FRONTEND" == false && "$BUILD_MINERU_CPU" == true ]]; then
    DEPLOY_HINT="  # 本次仅更新了 mineru:cpu
  docker compose ${COMPOSE_FILES} pull mineru
  docker compose ${COMPOSE_FILES} --profile mineru up -d --no-build
  docker compose ${COMPOSE_FILES} up -d --no-build --force-recreate backend"
  elif [[ "$BUILD_BACKEND" == false && "$BUILD_FRONTEND" == false && "$BUILD_MINERU_GPU" == true ]]; then
    DEPLOY_HINT="  # 本次仅更新了 mineru:gpu（.env：MINERU_BACKEND=vlm-vllm-engine，MINERU_BASE_URL=http://mineru-gpu:8000）
  docker compose ${COMPOSE_FILES} pull mineru-gpu
  docker compose ${COMPOSE_FILES} --profile mineru-gpu up -d --no-build
  docker compose ${COMPOSE_FILES} up -d --no-build --force-recreate backend"
  else
    DEPLOY_HINT="  # 全量更新或首次部署
  docker compose ${COMPOSE_FILES} pull
  docker compose ${COMPOSE_FILES} up -d --no-build
  # 首次部署或有新数据库迁移时执行：
  docker compose ${COMPOSE_FILES} exec backend python -m alembic upgrade head"
  fi
fi

# 避免在 heredoc 内写 $( echo '...' )：替换后会在行尾留下孤立的 '，若被误解析为 shell 会触发 s: command not found
_offline_suffix=""
[[ "$OFFLINE" == true ]] && _offline_suffix=", offline build"
_prod_suffix=""
[[ "$MODE" == "prod" ]] && _prod_suffix=" prod 部署"
_vite_api_hint="${VITE_API_BASE_URL:-（空，同源 nginx 反代）}"

cat <<EOF

================================================================================
推送完成（${MODE}${_offline_suffix}）。

【目标机 192.168.252.115】${_prod_suffix}
${DEPLOY_HINT}

  前端: http://192.168.252.115:8090
  后端: http://192.168.252.115:8091/docs
  前端 API 已写入镜像: ${_vite_api_hint}
================================================================================
EOF
