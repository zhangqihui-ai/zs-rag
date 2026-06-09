#!/usr/bin/env bash
set -euo pipefail
ROOT="$(cd "$(dirname "$0")/.." && pwd)"
PID_FILE="${ROOT}/logs/lightrag-progress-monitor.loop.pid"
if [[ ! -f "${PID_FILE}" ]]; then
  echo "No loop pid file"
  exit 0
fi
PID=$(cat "${PID_FILE}")
if kill "${PID}" 2>/dev/null; then
  echo "Stopped loop pid ${PID}"
else
  echo "Loop pid ${PID} not running"
fi
rm -f "${PID_FILE}"
