#!/usr/bin/env bash
# Background loop: every 3m run monitor tick + AGENT_LOOP_TICK sentinel.
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="${ROOT}/logs/lightrag-progress-monitor.loop.pid"
INTERVAL_SEC="${INTERVAL_SEC:-180}"

mkdir -p "${ROOT}/logs"

if [[ -f "${PID_FILE}" ]]; then
  OLD_PID=$(cat "${PID_FILE}")
  if kill -0 "${OLD_PID}" 2>/dev/null; then
    echo "Loop already running (pid ${OLD_PID})"
    exit 0
  fi
fi

(
  while true; do
    sleep "${INTERVAL_SEC}"
    echo 'AGENT_LOOP_TICK_lightrag_progress {"prompt":"Check LightRAG progress log and report changes"}'
    "${ROOT}/scripts/run-lightrag-progress-monitor-tick.sh" || true
  done
) &

echo $! > "${PID_FILE}"
echo "Started lightrag progress loop pid=$(cat "${PID_FILE}") interval=${INTERVAL_SEC}s"
