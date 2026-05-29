#!/usr/bin/env sh
# 启动前确保 local 模式有 mineru.json（兼容旧离线镜像 / 手工导入模型）
set -eu
if [ "${MINERU_MODEL_SOURCE:-}" = "local" ]; then
  /usr/local/bin/generate-mineru-local-config.sh /models || true
fi
exec "$@"
