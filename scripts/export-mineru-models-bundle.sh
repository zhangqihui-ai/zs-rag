#!/usr/bin/env bash
# 将已预热成功的 MinerU /models 导出到 backend/mineru_models_bundle/，供 Dockerfile.mineru-cpu 打进镜像。
#
# 前置：有网环境，MinerU 已至少成功 file_parse 一次（/models 约 1GB+）。
#
# 用法（任选其一）：
#   ./scripts/export-mineru-models-bundle.sh                    # 从运行中的容器 zs-rag-mineru 导出
#   ./scripts/export-mineru-models-bundle.sh zs-rag-mineru-cpu
#   ./scripts/export-mineru-models-bundle.sh --volume zs-rag_mineru_models
#
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT_DIR="${ROOT_DIR}/backend/mineru_models_bundle"
CONTAINER=""
VOLUME=""

usage() {
  sed -n '1,12p' "$0"
  exit "${1:-0}"
}

while [[ $# -gt 0 ]]; do
  case "$1" in
    -h|--help) usage 0 ;;
    --volume) VOLUME="$2"; shift 2 ;;
    --*) echo "未知参数: $1" >&2; usage 1 ;;
    *)
      if [[ -z "$CONTAINER" ]]; then
        CONTAINER="$1"
      else
        echo "多余参数: $1" >&2; exit 1
      fi
      shift
      ;;
  esac
done

CONTAINER="${CONTAINER:-zs-rag-mineru}"
mkdir -p "$OUT_DIR"
rm -rf "${OUT_DIR:?}"/*
mkdir -p "$OUT_DIR"

log() { printf '[%s] %s\n' "$(date '+%H:%M:%S')" "$*"; }

if [[ -n "$VOLUME" ]]; then
  log "从卷 ${VOLUME} 导出到 ${OUT_DIR}"
  docker run --rm -v "${VOLUME}:/data:ro" -v "${OUT_DIR}:/out" alpine \
    sh -c "cp -a /data/. /out/ && rm -rf /out/.lock 2>/dev/null || true"
elif docker ps --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  log "从容器 ${CONTAINER} 导出到 ${OUT_DIR}"
  docker cp "${CONTAINER}:/models/." "$OUT_DIR/"
  rm -rf "${OUT_DIR}/.lock" 2>/dev/null || true
else
  echo "错误: 容器 ${CONTAINER} 未运行，且未指定 --volume。" >&2
  echo "  示例: docker compose --profile mineru up -d && $0" >&2
  echo "  或:   $0 --volume zs-rag_mineru_models" >&2
  exit 1
fi

# 去掉导出过程中的临时锁，避免离线启动误判
rm -rf "${OUT_DIR}/.lock" 2>/dev/null || true

bytes="$(find "$OUT_DIR" -type f -printf '%s\n' 2>/dev/null | awk '{s+=$1} END {print s+0}')"
files="$(find "$OUT_DIR" -type f 2>/dev/null | wc -l | tr -d ' ')"
if [[ "${bytes:-0}" -lt 50000000 ]]; then
  echo "警告: 导出仅约 $(( bytes / 1024 / 1024 ))MB（${files} 个文件），可能未完整预热。" >&2
  echo "  请先在容器内 curl file_parse 直到 HTTP 200，再重新运行本脚本。" >&2
  exit 1
fi

if [[ -x "${ROOT_DIR}/backend/scripts/generate-mineru-local-config.sh" ]]; then
  log "生成 mineru.json（MINERU_MODEL_SOURCE=local 必需）"
  sh "${ROOT_DIR}/backend/scripts/generate-mineru-local-config.sh" "$OUT_DIR"
else
  echo "警告: 未找到 generate-mineru-local-config.sh，离线镜像需自行写入 mineru.json" >&2
fi

log "导出完成: $(du -sh "$OUT_DIR" | awk '{print $1}'), ${files} 个文件"
log "下一步: ./scripts/build-mineru-cpu-offline.sh --push"
log "  或: ./scripts/push-images-to-registry.sh --offline --mineru-offline-only"
log "  或: docker build -f backend/Dockerfile.mineru-cpu -t zs-rag-mineru:cpu backend"
