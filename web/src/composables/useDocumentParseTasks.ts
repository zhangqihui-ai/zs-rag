import { reactive } from 'vue'

import {
  cancelDocumentProcess,
  knowledgeBaseApi,
  streamDocumentProcess,
  type DocumentProcessStreamMode,
  type DocumentProgressPayload,
  type KnowledgeDocument,
  type KnowledgeDocumentParseLog,
} from '../api/knowledge-base'

export type DocumentParseTaskStatus = 'running' | 'success' | 'error' | 'cancelled'

/** 图知识库重建索引 SSE 的全局最大并发数（避免占满浏览器连接池） */
export const GRAPH_REINDEX_MAX_CONCURRENCY = 2

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

export interface DocumentParseTaskStartOptions {
  force?: boolean
  /** 图知识库：受 GRAPH_REINDEX_MAX_CONCURRENCY 闸门限制 */
  graphKb?: boolean
  batchId?: string | null
  onTerminal?: (document: KnowledgeDocument) => void
}

const PROCESSING_STATUSES = new Set(['parsing', 'chunking', 'indexing', 'graph_indexing'])

const STATUS_PERCENT: Record<string, number> = {
  queued: 3,
  parsing: 8,
  chunking: 20,
  embedding: 28,
  indexing: 72,
  graph_indexing: 55,
}

function capRunningPercent(percent: number): number {
  if (!Number.isFinite(percent)) {
    return 0
  }
  return Math.min(Math.max(percent, 0), 99)
}

const globalTasks = reactive(new Map<string, DocumentParseTask>())
const watchPollers = new Map<string, number>()
/** 用户在本会话内主动取消的文档，避免 refresh 后 reconcile 再次 resumeWatch */
const userCancelledKeys = new Set<string>()

class AsyncSemaphore {
  private inUse = 0
  private readonly queue: Array<{
    resolve: () => void
    reject: (error: Error) => void
  }> = []

  constructor(private readonly max: number) {}

  get waitingCount(): number {
    return this.queue.length
  }

  get activeCount(): number {
    return this.inUse
  }

  async acquire(signal?: AbortSignal): Promise<() => void> {
    if (signal?.aborted) {
      throw new DOMException('Aborted', 'AbortError')
    }
    if (this.inUse < this.max) {
      this.inUse += 1
      return () => this.release()
    }
    await new Promise<void>((resolve, reject) => {
      const entry = {
        resolve: () => {
          this.inUse += 1
          resolve()
        },
        reject,
      }
      this.queue.push(entry)
      signal?.addEventListener(
        'abort',
        () => {
          const index = this.queue.indexOf(entry)
          if (index >= 0) {
            this.queue.splice(index, 1)
          }
          reject(new DOMException('Aborted', 'AbortError'))
        },
        { once: true },
      )
    })
    return () => this.release()
  }

  private release() {
    this.inUse = Math.max(0, this.inUse - 1)
    const next = this.queue.shift()
    next?.resolve()
  }
}

const graphReindexSemaphore = new AsyncSemaphore(GRAPH_REINDEX_MAX_CONCURRENCY)

function taskKey(kbId: number, documentId: number) {
  return `${kbId}:${documentId}`
}

function clearUserCancelled(kbId: number, documentId: number) {
  userCancelledKeys.delete(taskKey(kbId, documentId))
}

function markUserCancelled(kbId: number, documentId: number) {
  userCancelledKeys.add(taskKey(kbId, documentId))
}

export function wasUserCancelledParseTask(kbId: number, documentId: number): boolean {
  return userCancelledKeys.has(taskKey(kbId, documentId))
}

function snapshotStorageKey(kbId: number, documentId: number) {
  return `zs-rag-parse-task:${kbId}:${documentId}`
}

function clearTaskSnapshot(kbId: number, documentId: number) {
  try {
    sessionStorage.removeItem(snapshotStorageKey(kbId, documentId))
  } catch {
    /* quota */
  }
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

function statusToPercent(status: string): number {
  return STATUS_PERCENT[status] ?? 5
}

function normalizeProgressPayload(payload: DocumentProgressPayload): DocumentProgressPayload {
  if (payload.phase === 'success' || payload.phase === 'done') {
    return { ...payload, phase: 'done', percent: 100, message: payload.message || '完成' }
  }
  if (payload.phase === 'error') {
    return { ...payload, percent: payload.percent || 0, message: payload.message || '失败' }
  }
  if (payload.phase === 'running' && payload.percent <= 0) {
    return { ...payload, percent: 5 }
  }
  return payload
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

function isAbortError(error: unknown): boolean {
  if (error instanceof DOMException && error.name === 'AbortError') {
    return true
  }
  return error instanceof Error && error.name === 'AbortError'
}

async function documentStillProcessing(kbId: number, documentId: number): Promise<boolean> {
  try {
    const doc = await knowledgeBaseApi.getDocument(kbId, documentId)
    return PROCESSING_STATUSES.has(doc.status)
  } catch {
    return false
  }
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
    const normalized = normalizeProgressPayload(payload)
    task.phase = normalized.phase
    task.percent =
      normalized.phase === 'done' || normalized.phase === 'success'
        ? 100
        : capRunningPercent(Math.max(task.percent, normalized.percent))
    if (normalized.message) {
      task.progressMessage = normalized.message
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

  function applyRemoteProgress(documentId: number, remote: KnowledgeDocumentParseLog) {
    const progress = remote.progress
    if (!progress || typeof progress.phase !== 'string') {
      return
    }
    updateProgress(documentId, {
      phase: progress.phase,
      percent: typeof progress.percent === 'number' ? progress.percent : 5,
      current: progress.current ?? null,
      total: progress.total ?? null,
      message: progress.message ?? '',
    })
  }

  async function syncLogsFromServer(documentId: number): Promise<boolean> {
    const id = resolveKbId()
    if (id == null) {
      return false
    }
    try {
      const remote = await knowledgeBaseApi.getDocumentParseLog(id, documentId)
      const task = getTask(documentId)
      if (!task) {
        return false
      }
      let changed = false
      const next = (remote.lines || []).map((line) => ({
        t: formatParseLogTime(line.t),
        text: line.text,
      }))
      if (next.length >= task.logs.length) {
        task.logs = next
        if (remote.kind === 'parse' || remote.kind === 'reindex') {
          task.mode = remote.kind
        }
        if (remote.phase === 'success') {
          task.status = 'success'
          task.percent = 100
          task.progressMessage = '完成'
        } else if (remote.phase === 'error') {
          task.status = 'error'
          task.progressMessage = '解析失败'
        } else if (remote.phase === 'running') {
          applyRemoteProgress(documentId, remote)
          if (task.percent < 5) {
            task.percent = 5
          }
        }
        changed = true
      } else if (remote.phase === 'running' && remote.progress) {
        applyRemoteProgress(documentId, remote)
        changed = true
      }
      if (changed) {
        persistTaskSnapshot(task)
        return true
      }
      return false
    } catch {
      return false
    }
  }

  function watchUntilTerminal(
    documentId: number,
    task: DocumentParseTask,
    options?: { onTerminal?: (document: KnowledgeDocument) => void },
  ): Promise<KnowledgeDocument | null> {
    const key = taskKey(task.kbId, documentId)
    stopWatchPoll(key)
    task.watchOnly = true
    if (task.status === 'error') {
      task.status = 'running'
    }
    persistTaskSnapshot(task)

    return new Promise((resolve) => {
      const poll = async () => {
        if (task.abortController.signal.aborted) {
          stopWatchPoll(key)
          task.status = 'cancelled'
          persistTaskSnapshot(task)
          resolve(null)
          return
        }
        try {
          await syncLogsFromServer(documentId)
          const doc = await knowledgeBaseApi.getDocument(task.kbId, documentId)
          const current = globalTasks.get(key)
          if (!current) {
            stopWatchPoll(key)
            resolve(null)
            return
          }
          if (current.status !== 'running') {
            stopWatchPoll(key)
            if (current.status === 'success') {
              current.percent = 100
              options?.onTerminal?.(doc)
              globalTasks.delete(key)
              resolve(doc)
            } else {
              globalTasks.delete(key)
              resolve(null)
            }
            return
          }
          if (PROCESSING_STATUSES.has(doc.status)) {
            current.phase = doc.status
            await syncLogsFromServer(documentId)
            if (current.percent <= 0) {
              current.percent = statusToPercent(doc.status)
            }
            if (!current.progressMessage) {
              current.progressMessage = `状态：${doc.status}`
            }
            persistTaskSnapshot(current)
            return
          }
          stopWatchPoll(key)
          current.status = doc.status === 'failed' || doc.status === 'graph_failed' ? 'error' : 'success'
          current.percent = 100
          current.progressMessage = current.status === 'error' ? '解析失败' : '完成'
          persistTaskSnapshot(current)
          options?.onTerminal?.(doc)
          globalTasks.delete(key)
          resolve(doc)
        } catch {
          /* 网络抖动时继续轮询 */
        }
      }

      void poll()
      const timer = window.setInterval(() => {
        void poll()
      }, 2000)
      watchPollers.set(key, timer)
    })
  }

  async function resumeWatch(
    documentId: number,
    options: {
      status: string
      mode?: DocumentProcessStreamMode
      onTerminal?: (document: KnowledgeDocument) => void
    },
  ): Promise<void> {
    const id = resolveKbId()
    if (id == null || isRunning(documentId)) {
      return
    }

    const key = taskKey(id, documentId)
    stopWatchPoll(key)

    const stored = loadTaskSnapshot(id, documentId)
    const mode = options.mode ?? stored?.mode ?? 'parse'
    const abortController = new AbortController()
    clearTaskSnapshot(id, documentId)
    const task: DocumentParseTask = {
      documentId,
      kbId: id,
      mode,
      phase: stored?.phase ?? options.status,
      percent: statusToPercent(options.status),
      progressMessage: '解析进行中…',
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

    // 后台轮询，不阻塞页面加载（reconcileProcessingTasks 等调用方）
    void watchUntilTerminal(documentId, task, { onTerminal: options.onTerminal })
  }

  async function fallbackToWatchAfterSseDrop(
    documentId: number,
    task: DocumentParseTask,
    options?: DocumentParseTaskStartOptions,
  ): Promise<KnowledgeDocument | null> {
    const stillRunning = await documentStillProcessing(task.kbId, documentId)
    if (!stillRunning) {
      return null
    }
    appendLog(documentId, '实时流已断开，已切换为轮询跟踪（后台任务仍在运行）')
    return watchUntilTerminal(documentId, task, { onTerminal: options?.onTerminal })
  }

  async function startTask(
    documentId: number,
    mode: DocumentProcessStreamMode,
    options?: DocumentParseTaskStartOptions,
  ): Promise<KnowledgeDocument | null> {
    const id = resolveKbId()
    if (id == null) {
      return null
    }

    const key = taskKey(id, documentId)
    stopWatchPoll(key)

    const existing = globalTasks.get(key)
    if (existing?.status === 'running') {
      existing.abortController.abort()
    }

    const abortController = new AbortController()
    clearTaskSnapshot(id, documentId)
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
    clearUserCancelled(id, documentId)
    appendLog(documentId, mode === 'reindex' ? '正在连接重建索引流…' : '正在连接解析流…')

    const needsGraphSlot = Boolean(options?.graphKb && mode === 'reindex')
    let releaseGraphSlot: (() => void) | null = null

    try {
      if (needsGraphSlot) {
        if (graphReindexSemaphore.waitingCount > 0 || graphReindexSemaphore.activeCount >= GRAPH_REINDEX_MAX_CONCURRENCY) {
          appendLog(
            documentId,
            `图库重建任务较多，排队等待空闲名额（当前 ${graphReindexSemaphore.activeCount}/${GRAPH_REINDEX_MAX_CONCURRENCY}）…`,
          )
        }
        releaseGraphSlot = await graphReindexSemaphore.acquire(abortController.signal)
      }

      const result = await streamDocumentProcess(id, documentId, mode, {
        force: options?.force,
        batchId: options?.batchId,
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
          /* 错误由 catch 统一处理，便于 SSE 断线后切轮询 */
        },
      })
      if (task.status === 'cancelled') {
        return result
      }
      task.status = 'success'
      task.percent = 100
      persistTaskSnapshot(task)
      options?.onTerminal?.(result)
      finishTask(documentId)
      return result
    } catch (error) {
      if (isAbortError(error) || abortController.signal.aborted || task.status === 'cancelled') {
        task.status = 'cancelled'
        persistTaskSnapshot(task)
        return null
      }

      const watched = await fallbackToWatchAfterSseDrop(documentId, task, options)
      if (watched) {
        options?.onTerminal?.(watched)
        return watched
      }

      task.status = 'error'
      task.progressMessage = '解析失败'
      persistTaskSnapshot(task)
      throw error
    } finally {
      releaseGraphSlot?.()
    }
  }

  async function cancelTask(documentId: number): Promise<KnowledgeDocument | null> {
    const id = resolveKbId()
    if (id == null) {
      return null
    }

    const key = taskKey(id, documentId)
    markUserCancelled(id, documentId)
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
      globalTasks.delete(key)
      return doc
    } catch (error) {
      if (task) {
        task.status = 'cancelled'
        appendLog(documentId, '【已取消】用户停止了解析')
      }
      globalTasks.delete(key)
      throw error
    }
  }

  function reconcileTaskTerminalState(documentId: number, status: string) {
    const task = getTask(documentId)
    if (!task || task.status !== 'running') {
      return
    }
    // 用户主动发起的 SSE 任务由 startTask 自己收尾，列表刷新不应提前 finish
    if (!task.watchOnly) {
      return
    }
    if (PROCESSING_STATUSES.has(status)) {
      return
    }
    task.status = status === 'failed' || status === 'graph_failed' ? 'error' : 'success'
    task.percent = 100
    task.progressMessage = ''
    persistTaskSnapshot(task)
    finishTask(documentId)
  }

  function finishTask(documentId: number) {
    const id = resolveKbId()
    if (id == null) {
      return
    }
    const key = taskKey(id, documentId)
    stopWatchPoll(key)
    try {
      sessionStorage.removeItem(snapshotStorageKey(id, documentId))
    } catch {
      /* ignore */
    }
    globalTasks.delete(key)
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
    reconcileTaskTerminalState,
    finishTask,
  }
}
