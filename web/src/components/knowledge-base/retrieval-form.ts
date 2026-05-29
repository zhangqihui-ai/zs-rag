import type { KnowledgeBase, RetrievalMode } from '../../api/knowledge-base'
import { knowledgeBaseApi } from '../../api/knowledge-base'
import type { FusionMethod, HybridStrategy, RetrievalFormState } from './RetrievalConfigForm.vue'

export type { FusionMethod, HybridStrategy, RetrievalFormState }

export interface StoredRetrievalConfig {
  vector_weight?: number
  hybrid_strategy?: HybridStrategy
  fusion_method?: FusionMethod
  rerank_enabled?: boolean
  rerank_model_id?: number | null
  score_threshold_enabled?: boolean
  include_image_ocr?: boolean
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
    fusion_method:
      stored.fusion_method === 'weighted' || stored.fusion_method === 'rrf'
        ? stored.fusion_method
        : undefined,
    rerank_enabled:
      typeof stored.rerank_enabled === 'boolean' ? stored.rerank_enabled : undefined,
    rerank_model_id: typeof rerankId === 'number' ? rerankId : rerankId === null ? null : undefined,
    score_threshold_enabled:
      typeof stored.score_threshold_enabled === 'boolean'
        ? stored.score_threshold_enabled
        : undefined,
    include_image_ocr:
      typeof stored.include_image_ocr === 'boolean' ? stored.include_image_ocr : undefined,
  }
}

export function defaultRetrievalFormState(): RetrievalFormState {
  return {
    mode: 'hybrid',
    top_k: 5,
    score_threshold_enabled: true,
    score_threshold: 0.5,
    vector_weight: 0.3,
    hybrid_strategy: 'weight',
    fusion_method: 'weighted',
    rerank_enabled: false,
    rerank_model_id: null,
    include_image_ocr: false,
  }
}

/** 校验检索表单；通过返回 null，否则返回错误文案。 */
export function validateRetrievalForm(f: RetrievalFormState): string | null {
  if (f.top_k < 1 || f.top_k > 50 || !Number.isFinite(f.top_k)) {
    return 'Top K 取值范围为 1~50。'
  }
  if (f.score_threshold_enabled) {
    if (f.score_threshold < 0 || f.score_threshold > 1 || !Number.isFinite(f.score_threshold)) {
      return 'Score 阈值取值范围为 0~1。'
    }
  }
  if (f.mode === 'hybrid') {
    if (f.hybrid_strategy === 'weight') {
      if (f.vector_weight < 0 || f.vector_weight > 1 || !Number.isFinite(f.vector_weight)) {
        return '向量相似度权重取值范围为 0~1。'
      }
    } else if (!f.rerank_model_id) {
      return '请选择一个 Rerank 模型或切换到权重设置。'
    }
  } else if (f.rerank_enabled && !f.rerank_model_id) {
    return '已启用 Rerank，请选择一个 Rerank 模型。'
  }
  return null
}

/** 将表单状态转为知识库 update 载荷（与后端 knowledge_retrieval_defaults 对齐）。 */
export function buildRetrievalUpdatePayload(
  f: RetrievalFormState,
  currentConfig: Record<string, unknown> | null | undefined,
) {
  const prev = currentConfig || {}
  const retrievalStored: StoredRetrievalConfig = {
    vector_weight: f.vector_weight,
    hybrid_strategy: f.hybrid_strategy,
    fusion_method: f.fusion_method,
    rerank_enabled: f.rerank_enabled,
    rerank_model_id:
      f.mode === 'hybrid'
        ? f.hybrid_strategy === 'rerank'
          ? f.rerank_model_id
          : null
        : f.rerank_enabled
          ? f.rerank_model_id
          : null,
    score_threshold_enabled: f.score_threshold_enabled,
    include_image_ocr: f.include_image_ocr,
  }
  return {
    default_retrieval_mode: f.mode,
    default_top_k: Math.round(f.top_k),
    default_score_threshold: f.score_threshold_enabled ? f.score_threshold : null,
    config: { ...prev, retrieval: retrievalStored } as Record<string, unknown>,
  }
}

/** 从知识库详情构造检索表单初值。"设置面板"与"检索测试页"共用。 */
export function retrievalFormFromKnowledgeBase(kb: KnowledgeBase): RetrievalFormState {
  const stored = readStoredRetrieval(kb)
  const mode: RetrievalMode = kb.default_retrieval_mode
  const topK = Math.round(clampNumber(kb.default_top_k, 1, 50, defaultRetrievalFormState().top_k))
  let scoreThresholdEnabled = true
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
    vector_weight: clampNumber(stored.vector_weight, 0, 1, 0.3),
    hybrid_strategy: stored.hybrid_strategy || 'weight',
    fusion_method: stored.fusion_method || 'weighted',
    rerank_enabled: stored.rerank_enabled ?? false,
    rerank_model_id: stored.rerank_model_id ?? null,
    include_image_ocr: stored.include_image_ocr ?? false,
  }
}

/** 从已选知识库解析 Top K（与检索测试一致：取首个知识库的 default_top_k）。 */
export function topKFromKnowledgeBases(kbIds: number[], kbs: KnowledgeBase[]): number {
  const fallback = defaultRetrievalFormState().top_k
  if (kbIds.length === 0) {
    return fallback
  }
  const primary = kbs.find((k) => k.id === kbIds[0])
  if (!primary) {
    return fallback
  }
  return Math.round(clampNumber(primary.default_top_k, 1, 50, fallback))
}

/** 将 Top K 写入已选知识库 default_top_k（与检索设置 / 检索测试保存字段一致）。 */
export async function syncTopKToKnowledgeBases(
  kbIds: number[],
  topK: number,
  kbs: KnowledgeBase[],
): Promise<KnowledgeBase[]> {
  const value = Math.round(clampNumber(topK, 1, 50, defaultRetrievalFormState().top_k))
  const updated: KnowledgeBase[] = []
  for (const id of kbIds) {
    const kb = kbs.find((k) => k.id === id)
    if (!kb || kb.default_top_k === value) {
      if (kb) {
        updated.push(kb)
      }
      continue
    }
    const next = await knowledgeBaseApi.update(id, { default_top_k: value })
    updated.push(next)
  }
  return updated
}
