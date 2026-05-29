#!/usr/bin/env sh
# 为 MINERU_MODEL_SOURCE=local 生成 mineru.json（MinerU 必需，否则 local_models_config=None → 409）
# JSON 内路径一律为容器内 /models/...（与 MINERU_TOOLS_CONFIG_JSON=/models/mineru.json 一致）
#
# 用法：
#   generate-mineru-local-config.sh /models
#   generate-mineru-local-config.sh /path/to/mineru_models_bundle
set -eu

ROOT="${1:-/models}"
CONFIG="${ROOT}/mineru.json"

if [ -f "$CONFIG" ] && [ -s "$CONFIG" ]; then
  # 已存在且 pipeline 指向 /models 则跳过
  if grep -q '"/models/' "$CONFIG" 2>/dev/null; then
    echo "mineru.json already exists: $CONFIG"
    exit 0
  fi
fi

KIT=""
if [ -d "${ROOT}/models/OpenDataLab" ]; then
  KIT="$(find "${ROOT}/models/OpenDataLab" -maxdepth 1 -type d -name 'PDF-Extract-Kit*' 2>/dev/null | head -1)"
fi
if [ -z "$KIT" ] || [ ! -d "${KIT}/models" ]; then
  echo "错误: 在 ${ROOT} 下未找到 pipeline 模型（models/OpenDataLab/PDF-Extract-Kit*）" >&2
  exit 1
fi

REL="${KIT#"${ROOT}"}"
case "$REL" in
  /*) PIPELINE="/models${REL}" ;;
  *) PIPELINE="/models/${REL}" ;;
esac

cat > "$CONFIG" <<EOF
{
  "models-dir": {
    "pipeline": "${PIPELINE}",
    "vlm": ""
  },
  "config_version": "1.3.1"
}
EOF

echo "Wrote ${CONFIG} (pipeline=${PIPELINE})"
