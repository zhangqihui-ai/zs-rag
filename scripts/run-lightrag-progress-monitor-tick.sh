#!/usr/bin/env bash
set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
LOG_DIR="${ROOT}/logs"
LOG_FILE="${LOG_DIR}/lightrag-progress-monitor.log"
STATE_FILE="${LOG_DIR}/lightrag-progress-monitor.state"
STUCK_MINUTES="${STUCK_MINUTES:-15}"
LOW_CPU_PCT="${LOW_CPU_PCT:-8}"
TASK_START_UTC="${TASK_START_UTC:-2026-06-08T09:13:26+00:00}"

mkdir -p "${LOG_DIR}"

TASK_START_EPOCH=$(date -u -d "${TASK_START_UTC}" +%s 2>/dev/null || date -d "${TASK_START_UTC}" +%s 2>/dev/null || echo 0)

MON_OUT=""
if ! MON_OUT=$("${ROOT}/scripts/monitor-lightrag-progress.sh" 2>&1); then
  MON_OUT="${MON_OUT}"$'\n'"  ERROR: monitor script failed"
fi

STATS_LINE="unavailable"
CPU_NUM="999"
if STATS_LINE=$(docker stats zs-rag-celery-worker --no-stream --format '{{.CPUPerc}} {{.MemUsage}}' 2>/dev/null); then
  CPU_NUM=$(echo "${STATS_LINE}" | awk '{gsub(/%/,"",$1); print $1}')
fi

NEW_COMPLETE=$(echo "${MON_OUT}" | sed -n 's/.*new_complete_since_restart=\([0-9]*\).*/\1/p' | head -1)
DB_STATUS=$(echo "${MON_OUT}" | sed -n 's/.*db_status=\([^ ]*\).*/\1/p' | head -1)
[[ -z "${NEW_COMPLETE}" ]] && NEW_COMPLETE=0
[[ -z "${DB_STATUS}" ]] && DB_STATUS=unknown

NOW_EPOCH=$(date +%s)
ZERO_SINCE=""
if [[ -f "${STATE_FILE}" ]]; then
  # shellcheck disable=SC1090
  source "${STATE_FILE}" 2>/dev/null || true
fi

if [[ "${NEW_COMPLETE}" -gt 0 ]]; then
  ZERO_SINCE=""
elif [[ "${DB_STATUS}" == "graph_indexing" ]]; then
  if [[ -z "${ZERO_SINCE:-}" ]]; then
    if [[ "${TASK_START_EPOCH}" -gt 0 ]]; then
      ZERO_SINCE="${TASK_START_EPOCH}"
    else
      ZERO_SINCE="${NOW_EPOCH}"
    fi
  fi
else
  ZERO_SINCE=""
fi

{
  echo "======== $(date -Iseconds) ========"
  echo "${MON_OUT}"
  echo "--- worker stats ---"
  echo "  celery-worker CPU/MEM: ${STATS_LINE}"
} >> "${LOG_FILE}"

ALERT=""
if [[ "${DB_STATUS}" == "graph_indexed" ]]; then
  ALERT="  >>> INDEXING COMPLETE (graph_indexed) <<<"
elif [[ -n "${ZERO_SINCE:-}" ]]; then
  ELAPSED=$(( NOW_EPOCH - ZERO_SINCE ))
  if (( ELAPSED >= STUCK_MINUTES * 60 )); then
    CPU_CMP=$(echo "${CPU_NUM}" | awk -v lim="${LOW_CPU_PCT}" '{ if ($1+0 < lim+0) print 1; else print 0 }')
    if [[ "${CPU_CMP}" == "1" ]]; then
      ALERT="  STUCK_ALERT: new_complete=0 for ${ELAPSED}s (~$((ELAPSED/60))m) and CPU=${CPU_NUM}% (<${LOW_CPU_PCT}%)"
    fi
  fi
fi

if [[ -n "${ALERT}" ]]; then
  echo "${ALERT}" >> "${LOG_FILE}"
fi

{
  echo "zero_since_epoch=${ZERO_SINCE:-}"
  echo "last_new_complete=${NEW_COMPLETE}"
  echo "last_db_status=${DB_STATUS}"
  echo "last_tick_epoch=${NOW_EPOCH}"
} > "${STATE_FILE}"
