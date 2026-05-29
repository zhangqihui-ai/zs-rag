#!/usr/bin/env bash
# 下载 Docling layout/table 模型到 offline_deps（内网构建用）。
# 用法（在 backend/ 目录）：
#   ./scripts/download-odl-hybrid-docling-models.sh
# 可选：HF_MIRROR=https://hf-mirror.com
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
OUT="${ROOT}/offline_deps/docling-models"
HF_MIRROR="${HF_MIRROR:-${HF_ENDPOINT:-https://hf-mirror.com}}"
HF_MIRROR="${HF_MIRROR%/}"

mkdir -p "${OUT}"

curl_file() {
  local repo="$1"
  local relpath="$2"
  local dest="$3"
  mkdir -p "$(dirname "${dest}")"
  local url="${HF_MIRROR}/${repo}/resolve/main/${relpath}"
  echo "==> ${relpath}"
  curl -fsSL --connect-timeout 120 --retry 5 --retry-delay 5 -C - -o "${dest}" "${url}"
}

echo "HF mirror: ${HF_MIRROR}"
echo "Output:    ${OUT}"
echo

LAYOUT_DIR="${OUT}/docling-project--docling-layout-heron"
TABLE_DIR="${OUT}/docling-project--docling-models"

echo "--- layout: docling-project/docling-layout-heron ---"
curl_file "docling-project/docling-layout-heron" "config.json" \
  "${LAYOUT_DIR}/config.json"
curl_file "docling-project/docling-layout-heron" "preprocessor_config.json" \
  "${LAYOUT_DIR}/preprocessor_config.json"
curl_file "docling-project/docling-layout-heron" "model.safetensors" \
  "${LAYOUT_DIR}/model.safetensors"

echo
echo "--- table: docling-project/docling-models ---"
curl_file "docling-project/docling-models" "config.json" \
  "${TABLE_DIR}/config.json"
curl_file "docling-project/docling-models" \
  "model_artifacts/tableformer/fast/tm_config.json" \
  "${TABLE_DIR}/model_artifacts/tableformer/fast/tm_config.json"
curl_file "docling-project/docling-models" \
  "model_artifacts/tableformer/fast/tableformer_fast.safetensors" \
  "${TABLE_DIR}/model_artifacts/tableformer/fast/tableformer_fast.safetensors"
curl_file "docling-project/docling-models" \
  "model_artifacts/tableformer/accurate/tm_config.json" \
  "${TABLE_DIR}/model_artifacts/tableformer/accurate/tm_config.json"
curl_file "docling-project/docling-models" \
  "model_artifacts/tableformer/accurate/tableformer_accurate.safetensors" \
  "${TABLE_DIR}/model_artifacts/tableformer/accurate/tableformer_accurate.safetensors"

echo
echo "Done."
du -sh "${LAYOUT_DIR}" "${TABLE_DIR}"
