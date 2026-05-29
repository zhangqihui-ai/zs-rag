#!/usr/bin/env bash
# 打包 prod 离线部署所需的最小文件集（不含源码）
set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
OUT="${1:-${ROOT_DIR}/zs-rag-prod-deploy-bundle.tar.gz}"

cd "$ROOT_DIR"
tar -czvf "$OUT" \
  docker-compose.prod.yml \
  docker-compose.prod.registry.yml \
  .env.template

echo ""
echo "已生成: $OUT"
echo "目标机解压后: cp .env.template .env && 编辑 .env && docker compose -f docker-compose.prod.yml -f docker-compose.prod.registry.yml pull"
