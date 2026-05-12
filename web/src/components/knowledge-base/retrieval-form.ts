import type { KnowledgeBase, RetrievalMode } from '../../api/knowledge-base'
import type { HybridStrategy, RetrievalFormState } from './RetrievalConfigForm.vue'

export interface StoredRetrievalConfig {
  vector_weight?: number
  hybrid_strategy?: HybridStrategy
  rerank_enabled?: boolean
  rerank_model_id?: number | null
  score_threshold_enabled?: boolean
}

export function clampNumber(value: unknown, min: number, max: number, fallback: number): number {
  const num = typeof value === 'number' ? value : Number(value)
  if (!Number.isFinite(num)) {
    return fallback
  }
  return Math.min(Math.max(num, min), max)
}

export function readStoredRetrieval(kb: KnowledgeBase): StoredRetrievalConfig {
  const cfg = kb.config as Record<string, unknown> | null
  const stored = (cfg && typeof cfg === 'object' ? cfg.retrieval : null) as
    | Record<string, unknown>
    | null
    | undefined
  if (!stored || typeof stored !== 'object') {
    return {}
  }
  const rerankId = stored.rerank_model_id
  return {
    vector_weight: typeof stored.vector_weight === 'number' ? stored.vector_weight : undefined,
    hybrid_strategy:
      stored.hybrid_strategy === 'weight' || stored.hybrid_strategy === 'rerank'
        ? stored.hybrid_strategy
        : undefined,
    rerank_enabled:
      typeof stored.rerank_enabled === 'boolean' ? stored.rerank_enabled : undefined,
    rerank_model_id: typeof rerankId === 'number' ? rerankId : rerankId === null ? null : undefined,
    score_threshold_enabled:
      typeof stored.score_threshold_enabled === 'boolean'
        ? stored.score_threshold_enabled
        : undefined,
  }
}

export function defaultRetrievalFormState(): RetrievalFormState {
  return {
    mode: 'hybrid',
    top_k: 5,
    score_threshold_enabled: false,
    score_threshold: 0.5,
    vector_weight: 0.5,
    hybrid_strategy: 'weight',
    rerank_enabled: false,
    rerank_model_id: null,
  }
}

/** 从知识库详情构造检索表单初值。"设置面板"与"检索测试页"共用。 */
export function retrievalFormFromKnowledgeBase(kb: KnowledgeBase): RetrievalFormState {
  const stored = readStoredRetrieval(kb)
  const mode: RetrievalMode = kb.default_retrieval_mode
  const topK = Math.round(clampNumber(kb.default_top_k, 1, 50, 3))
  let scoreThresholdEnabled = false
  let scoreThreshold = 0.5
  if (kb.default_score_threshold != null) {
    scoreThresholdEnabled = true
    scoreThreshold = clampNumber(kb.default_score_threshold, 0, 1, 0.5)
  } else if (stored.score_threshold_enabled != null) {
    scoreThresholdEnabled = stored.score_threshold_enabled
  }
  return {
    mode,
    top_k: topK,
    score_threshold_enabled: scoreThresholdEnabled,
    score_threshold: scoreThreshold,
    vector_weight: clampNumber(stored.vector_weight, 0, 1, 0.5),
    hybrid_strategy: stored.hybrid_strategy || 'weight',
    rerank_enabled: stored.rerank_enabled ?? false,
    rerank_model_id: stored.rerank_model_id ?? null,
  }
}
