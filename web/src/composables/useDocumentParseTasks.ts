import { reactive } from 'vue'

import {
  cancelDocumentProcess,
  streamDocumentProcess,
  type DocumentProcessStreamMode,
  type DocumentProgressPayload,
  type KnowledgeDocument,
} from '../api/knowledge-base'

export type DocumentParseTaskStatus = 'running' | 'success' | 'error' | 'cancelled'

export interface DocumentParseTask {
  documentId: number
  mode: DocumentProcessStreamMode
  phase: string
  percent: number
  progressMessage: string
  status: DocumentParseTaskStatus
  logs: { t: string; text: string }[]
  abortController: AbortController
}

export function useDocumentParseTasks(kbId: () => number | undefined) {
  const tasks = reactive(new Map<number, DocumentParseTask>())

  function getTask(documentId: number): DocumentParseTask | undefined {
    return tasks.get(documentId)
  }

  function isRunning(documentId: number): boolean {
    return tasks.get(documentId)?.status === 'running'
  }

  function runningDocumentIds(): number[] {
    return [...tasks.values()]
      .filter((task) => task.status === 'running')
      .map((task) => task.documentId)
  }

  function appendLog(documentId: number, text: string) {
    const task = tasks.get(documentId)
    if (!task) {
      return
    }
    const t = new Date().toLocaleTimeString('zh-CN', { hour12: false })
    task.logs.push({ t, text })
  }

  function updateProgress(documentId: number, payload: DocumentProgressPayload) {
    const task = tasks.get(documentId)
    if (!task) {
      return
    }
    task.phase = payload.phase
    task.percent = payload.percent
    if (payload.message) {
      task.progressMessage = payload.message
    }
  }

  async function startTask(
    documentId: number,
    mode: DocumentProcessStreamMode,
    options?: { force?: boolean },
  ): Promise<KnowledgeDocument | null> {
    const id = kbId()
    if (!id || Number.isNaN(id)) {
      return null
    }

    const existing = tasks.get(documentId)
    if (existing?.status === 'running') {
      existing.abortController.abort()
    }

    const abortController = new AbortController()
    const task: DocumentParseTask = {
      documentId,
      mode,
      phase: mode === 'reindex' ? 'graph_indexing' : 'parsing',
      percent: 0,
      progressMessage: '',
      status: 'running',
      logs: [],
      abortController,
    }
    tasks.set(documentId, task)
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
        },
        onCancelled: () => {
          task.status = 'cancelled'
        },
        onError: () => {
          if (task.status === 'running') {
            task.status = 'error'
          }
        },
      })
      if (task.status === 'cancelled') {
        return result
      }
      task.status = 'success'
      task.percent = 100
      return result
    } catch (error) {
      if (abortController.signal.aborted || task.status === 'cancelled') {
        task.status = 'cancelled'
        return null
      }
      task.status = 'error'
      throw error
    }
  }

async function cancelTask(documentId: number): Promise<KnowledgeDocument | null> {
    const id = kbId()
    if (!id || Number.isNaN(id)) {
      return null
    }

    const task = tasks.get(documentId)
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
    tasks,
    getTask,
    isRunning,
    runningDocumentIds,
    startTask,
    cancelTask,
    appendLog,
  }
}
