import { defineStore } from 'pinia'
import { ref } from 'vue'

import {
  streamAgenticRAG,
  type AgenticRAGCompleteResponse,
  type AgenticRAGQueryRequest,
  type AgenticRAGTraceEvent,
} from '../api/agentic-rag'
import type { ChatCitation } from '../api/chat'

export const useAgenticRagStore = defineStore('agentic-rag', () => {
  const running = ref(false)
  const answer = ref('')
  const citations = ref<ChatCitation[]>([])
  const trace = ref<AgenticRAGTraceEvent[]>([])
  const error = ref('')
  const routeDecision = ref<string | null>(null)
  const routeReason = ref<string | null>(null)
  const iterations = ref(0)
  const currentQuery = ref<string | null>(null)
  const controller = ref<AbortController | null>(null)

  function resetResult() {
    answer.value = ''
    citations.value = []
    trace.value = []
    error.value = ''
    routeDecision.value = null
    routeReason.value = null
    iterations.value = 0
    currentQuery.value = null
  }

  async function run(payload: AgenticRAGQueryRequest) {
    controller.value?.abort()
    controller.value = new AbortController()
    running.value = true
    resetResult()
    try {
      await streamAgenticRAG(
        payload,
        (event) => {
          if (event.type === 'step_completed') {
            trace.value = [...trace.value, event.trace]
            routeDecision.value = event.route_decision ?? routeDecision.value
            iterations.value = event.iterations ?? iterations.value
            return
          }
          if (event.type === 'assistant_delta') {
            answer.value += event.content
            return
          }
          if (event.type === 'assistant_done') {
            const done = event as AgenticRAGCompleteResponse & { type: 'assistant_done' }
            answer.value = done.answer
            citations.value = done.citations || []
            trace.value = done.trace || trace.value
            routeDecision.value = done.route_decision ?? null
            routeReason.value = done.route_reason ?? null
            iterations.value = done.iterations || 0
            currentQuery.value = done.current_query ?? null
            return
          }
          if (event.type === 'error') {
            error.value = event.message || 'Agentic RAG 执行失败'
          }
        },
        { signal: controller.value.signal },
      )
    } catch (e) {
      if (e instanceof DOMException && e.name === 'AbortError') {
        error.value = '已停止生成'
      } else {
        error.value = e instanceof Error ? e.message : 'Agentic RAG 执行失败'
      }
    } finally {
      running.value = false
      controller.value = null
    }
  }

  function stop() {
    controller.value?.abort()
    controller.value = null
    running.value = false
  }

  return {
    running,
    answer,
    citations,
    trace,
    error,
    routeDecision,
    routeReason,
    iterations,
    currentQuery,
    resetResult,
    run,
    stop,
  }
})
