import { reactive } from 'vue'

import {
  cancelDocumentProcess,
  knowledgeBaseApi,
  streamDocumentProcess,
  type DocumentProcessStreamMode,
  type DocumentProgressPayload,
  type KnowledgeDocument,
} from '../api/knowledge-base'

export type DocumentParseTaskStatus = 'running' | 'success' | 'error' | 'cancelled'

export interface DocumentParseTask {
  documentId: number
  kbId: number
  mode: DocumentProcessStreamMode
  phase: string
  percent: number
  progressMessage: string
  status: DocumentParseTaskStatus
  logs: { t: string; text: string }[]
  abortController: AbortController
  /** 仅轮询恢复进度时为 true，无 SSE 连接 */
  watchOnly?: boolean
}

const PROCESSING_STATUSES = new Set(['parsing', 'chunking', 'indexing', 'graph_indexing'])

const STATUS_PERCENT: Record<string, number> = {
  parsing: 8,
  chunking: 20,
  embedding: 45,
  indexing: 78,
  graph_indexing: 55,
}

const globalTasks = reactive(new Map<string, DocumentParseTask>())
const watchPollers = new Map<string, number>()

function taskKey(kbId: number, documentId: number) {
  return `${kbId}:${documentId}`
}

function snapshotStorageKey(kbId: number, documentId: number) {
  return `zs-rag-parse-task:${kbId}:${documentId}`
}

function persistTaskSnapshot(task: DocumentParseTask) {
  try {
    sessionStorage.setItem(
      snapshotStorageKey(task.kbId, task.documentId),
      JSON.stringify({
        mode: task.mode,
        phase: task.phase,
        percent: task.percent,
        status: task.status,
        progressMessage: task.progressMessage,
        logs: task.logs.slice(-200),
      }),
    )
  } catch {
    /* quota */
  }
}

function loadTaskSnapshot(kbId: number, documentId: number): Partial<DocumentParseTask> | null {
  try {
    const raw = sessionStorage.getItem(snapshotStorageKey(kbId, documentId))
    if (!raw) {
      return null
    }
    return JSON.parse(raw) as Partial<DocumentParseTask>
  } catch {
    return null
  }
}

function clearTaskSnapshot(kbId: number, documentId: number) {
  try {
    sessionStorage.removeItem(snapshotStorageKey(kbId, documentId))
  } catch {
    /* ignore */
  }
}

function statusToPercent(status: string): number {
  return STATUS_PERCENT[status] ?? 5
}

function formatParseLogTime(t: string): string {
  if (!t) {
    return ''
  }
  const d = new Date(t)
  if (!Number.isNaN(d.getTime())) {
    return d.toLocaleTimeString('zh-CN', { hour12: false })
  }
  return t
}

export function useDocumentParseTasks(kbId: () => number | undefined) {
  function resolveKbId(): number | null {
    const id = kbId()
    if (!id || Number.isNaN(id)) {
      return null
    }
    return id
  }

  function getTask(documentId: number): DocumentParseTask | undefined {
    const id = resolveKbId()
    if (id == null) {
      return undefined
    }
    return globalTasks.get(taskKey(id, documentId))
  }

  function isRunning(documentId: number): boolean {
    return getTask(documentId)?.status === 'running'
  }

  function runningDocumentIds(): number[] {
    const id = resolveKbId()
    if (id == null) {
      return []
    }
    const prefix = `${id}:`
    return [...globalTasks.values()]
      .filter((task) => task.kbId === id && task.status === 'running')
      .map((task) => task.documentId)
  }

  function appendLog(documentId: number, text: string) {
    const task = getTask(documentId)
    if (!task) {
      return
    }
    const t = new Date().toLocaleTimeString('zh-CN', { hour12: false })
    task.logs.push({ t, text })
    persistTaskSnapshot(task)
  }

  function updateProgress(documentId: number, payload: DocumentProgressPayload) {
    const task = getTask(documentId)
    if (!task) {
      return
    }
    task.phase = payload.phase
    task.percent = payload.percent
    if (payload.message) {
      task.progressMessage = payload.message
    }
    persistTaskSnapshot(task)
  }

  function stopWatchPoll(key: string) {
    const timer = watchPollers.get(key)
    if (timer != null) {
      window.clearInterval(timer)
      watchPollers.delete(key)
    }
  }

  async function syncLogsFromServer(documentId: number): Promise<boolean> {
    const id = resolveKbId()
    if (id == null) {
      return false
    }
    try {
      const remote = await knowledgeBaseApi.getDocumentParseLog(id, documentId)
      const task = getTask(documentId)
      if (!task || !remote.lines?.length) {
        return false
      }
      const next = remote.lines.map((line) => ({
        t: formatParseLogTime(line.t),
        text: line.text,
      }))
      if (next.length >= task.logs.length) {
        task.logs = next
        if (remote.kind === 'parse' || remote.kind === 'reindex') {
          task.mode = remote.kind
        }
        persistTaskSnapshot(task)
        return true
      }
      return false
    } catch {
      return false
    }
  }

  async function resumeWatch(
    documentId: number,
    options: {
      status: string
      mode?: DocumentProcessStreamMode
      onTerminal?: (document: KnowledgeDocument) => void
    },
  ) {
    const id = resolveKbId()
    if (id == null || isRunning(documentId)) {
      return
    }

    const key = taskKey(id, documentId)
    stopWatchPoll(key)

    const stored = loadTaskSnapshot(id, documentId)
    const mode = options.mode ?? stored?.mode ?? 'parse'
    const abortController = new AbortController()
    const task: DocumentParseTask = {
      documentId,
      kbId: id,
      mode,
      phase: stored?.phase ?? options.status,
      percent: stored?.percent ?? statusToPercent(options.status),
      progressMessage: stored?.progressMessage ?? '解析进行中…',
      status: 'running',
      logs: stored?.logs ? [...stored.logs] : [],
      abortController,
      watchOnly: true,
    }
    if (task.logs.length === 0) {
      await syncLogsFromServer(documentId)
    }
    if (task.logs.length === 0) {
      appendLog(documentId, '已恢复解析进度跟踪（后台任务仍在运行）')
    }
    globalTasks.set(key, task)

    const poll = async () => {
      if (abortController.signal.aborted) {
        return
      }
      try {
        await syncLogsFromServer(documentId)
        const doc = await knowledgeBaseApi.getDocument(id, documentId)
        const current = getTask(documentId)
        if (!current || current.status !== 'running') {
          return
        }
        if (PROCESSING_STATUSES.has(doc.status)) {
          current.phase = doc.status
          current.percent = Math.max(current.percent, statusToPercent(doc.status))
          current.progressMessage = `状态：${doc.status}`
          persistTaskSnapshot(current)
          return
        }
        stopWatchPoll(key)
        current.status = doc.status === 'failed' || doc.status === 'graph_failed' ? 'error' : 'success'
        current.percent = 100
        persistTaskSnapshot(current)
        options.onTerminal?.(doc)
      } catch {
        /* 网络抖动时继续轮询 */
      }
    }

    void poll()
    const timer = window.setInterval(() => {
      void poll()
    }, 4000)
    watchPollers.set(key, timer)
  }

  async function startTask(
    documentId: number,
    mode: DocumentProcessStreamMode,
    options?: { force?: boolean },
  ): Promise<KnowledgeDocument | null> {
    const id = resolveKbId()
    if (id == null) {
      return null
    }

    const key = taskKey(id, documentId)
    stopWatchPoll(key)

    const existing = globalTasks.get(key)
    if (existing?.status === 'running') {
      if (existing.watchOnly) {
        existing.abortController.abort()
      } else {
        existing.abortController.abort()
      }
    }

    const abortController = new AbortController()
    const task: DocumentParseTask = {
      documentId,
      kbId: id,
      mode,
      phase: mode === 'reindex' ? 'graph_indexing' : 'parsing',
      percent: 0,
      progressMessage: '',
      status: 'running',
      logs: [],
      abortController,
      watchOnly: false,
    }
    globalTasks.set(key, task)
    appendLog(documentId, mode === 'reindex' ? '正在连接重建索引流…' : '正在连接解析流…')

    try {
      const result = await streamDocumentProcess(id, documentId, mode, {
        force: options?.force,
        signal: abortController.signal,
        onLog: (line) => appendLog(documentId, line),
        onProgress: (payload) => updateProgress(documentId, payload),
        onDone: () => {
          task.status = 'success'
          task.percent = 100
          persistTaskSnapshot(task)
        },
        onCancelled: () => {
          task.status = 'cancelled'
          persistTaskSnapshot(task)
        },
        onError: () => {
          if (task.status === 'running') {
            task.status = 'error'
            persistTaskSnapshot(task)
          }
        },
      })
      if (task.status === 'cancelled') {
        return result
      }
      task.status = 'success'
      task.percent = 100
      persistTaskSnapshot(task)
      return result
    } catch (error) {
      if (abortController.signal.aborted || task.status === 'cancelled') {
        task.status = 'cancelled'
        persistTaskSnapshot(task)
        return null
      }
      task.status = 'error'
      persistTaskSnapshot(task)
      throw error
    }
  }

  async function cancelTask(documentId: number): Promise<KnowledgeDocument | null> {
    const id = resolveKbId()
    if (id == null) {
      return null
    }

    const key = taskKey(id, documentId)
    stopWatchPoll(key)

    const task = globalTasks.get(key)
    if (task?.status === 'running') {
      task.abortController.abort()
    }

    try {
      const doc = await cancelDocumentProcess(id, documentId)
      if (task) {
        task.status = 'cancelled'
        appendLog(documentId, '【已取消】用户停止了解析')
      }
      return doc
    } catch {
      if (task?.status === 'running') {
        task.status = 'cancelled'
        appendLog(documentId, '【已取消】用户停止了解析')
      }
      return null
    }
  }

  return {
    tasks: globalTasks,
    getTask,
    isRunning,
    runningDocumentIds,
    startTask,
    cancelTask,
    resumeWatch,
    appendLog,
    syncLogsFromServer,
  }
}
