import type { AgentTraceEvent } from '../api/chat'

export function agentTraceStepLabel(step: string): string {
  const map: Record<string, string> = {
    route: '路由判断',
    route_refine: '路由二次判断',
    retrieve: '知识检索',
    grade: '相关性评估',
    rewrite: '问题改写',
    generate: '生成回答',
  }
  return map[step] || step
}

function routeDecisionLabel(value: string): string {
  return value === 'direct' ? '直接回答' : '知识库检索'
}

function pathRecallByType(item: AgentTraceEvent): { classic: number; lightrag: number } {
  const paths = Array.isArray(item.path_results) ? item.path_results : []
  let classic = 0
  let lightrag = 0
  for (const row of paths) {
    const count = row.recalled_count ?? 0
    if (row.kb_type === 'lightrag') {
      lightrag += count
    } else {
      classic += count
    }
  }
  return { classic, lightrag }
}

function pathRecallTotal(item: AgentTraceEvent): number {
  const { classic, lightrag } = pathRecallByType(item)
  return classic + lightrag
}

function pathRecallSummaryText(item: AgentTraceEvent): string {
  const paths = Array.isArray(item.path_results) ? item.path_results : []
  if (paths.length === 0) {
    const preTotal = pathRecallTotal(item)
    return preTotal > 0 ? `各路召回 ${preTotal} 条 → 公平合并后 ` : '召回 '
  }
  const { classic, lightrag } = pathRecallByType(item)
  return `图检索召回 ${lightrag} 条，向量检索召回 ${classic} 条 → 公平合并后 `
}

function typeBreakdownText(item: AgentTraceEvent): string {
  const meta = item.merge_meta
  const breakdown = meta?.type_breakdown
  if (!breakdown) {
    return ''
  }
  const parts: string[] = []
  if (breakdown.classic) {
    parts.push(`向量 ${breakdown.classic}`)
  }
  if (breakdown.lightrag) {
    parts.push(`图 ${breakdown.lightrag}`)
  }
  return parts.length ? `（${parts.join(' + ')}）` : ''
}

export function agentTraceSummary(item: AgentTraceEvent): string {
  if (item.step === 'route') {
    const pass = item.route_pass != null ? `（第 ${item.route_pass} 轮）` : ''
    return `决策：${routeDecisionLabel(String(item.decision || 'retrieve'))}${pass}。${String(item.reason || '')}`
  }
  if (item.step === 'route_refine') {
    const preTotal = item.pre_retrieve_total ?? 0
    return `预检索试探 ${preTotal} 条后二次路由：${routeDecisionLabel(String(item.decision || 'retrieve'))}。${String(item.reason || '')}`
  }
  if (item.step === 'retrieve') {
    const cfgBits: string[] = []
    if (item.vector_top_k != null) {
      cfgBits.push(`向量 Top K=${item.vector_top_k}`)
    }
    if (item.lightrag_top_k != null) {
      cfgBits.push(`图 Top K=${item.lightrag_top_k}`)
    }
    const mergeTopK = item.merge_top_k ?? item.top_k
    if (mergeTopK != null) {
      cfgBits.push(`合并 Top K=${mergeTopK}`)
    }
    if (item.lightrag_query_mode) {
      cfgBits.push(`图模式=${item.lightrag_query_mode}`)
    }
    const cfgText = cfgBits.length ? `（${cfgBits.join('，')}）` : ''
    const preText = pathRecallSummaryText(item)
    const typeText = typeBreakdownText(item)
    return `第 ${item.iteration || 1} 轮查询「${item.query || ''}」${cfgText}，${preText}${item.total || 0} 条${typeText}。`
  }
  if (item.step === 'grade') {
    const relevant = item.relevant_count || 0
    const total = item.total || 0
    if (total > 0 && relevant === 0) {
      return `相关片段 ${relevant} / ${total}（召回的 ${total} 条均未达相关标准，评分需 ≥1 且 relevant=true）。`
    }
    return `相关片段 ${relevant} / ${total}。`
  }
  if (item.step === 'rewrite') {
    if (item.from) {
      return `由「${item.from}」改写为「${item.to || ''}」。`
    }
    return `改写为「${item.to || ''}」。`
  }
  if (item.step === 'generate') {
    return `生成 ${item.answer_chars || 0} 字，引用 ${item.citation_count || 0} 条。`
  }
  return '已完成。'
}

export function agentTraceRetrieveCandidates(item: AgentTraceEvent) {
  return Array.isArray(item.candidates) ? item.candidates : []
}

export function agentTracePathResults(item: AgentTraceEvent) {
  return Array.isArray(item.path_results) ? item.path_results : []
}

export function agentTraceMergeMeta(item: AgentTraceEvent) {
  return item.merge_meta ?? null
}

export function agentTraceGradeRows(item: AgentTraceEvent) {
  return Array.isArray(item.grades) ? item.grades : []
}

export function formatRetrievalScore(value: unknown): string {
  const n = Number(value)
  return Number.isFinite(n) ? n.toFixed(3) : '—'
}

export function formatGradeVerdict(relevant: boolean, gradeScore: unknown): string {
  const score = Number(gradeScore)
  if (relevant) {
    return Number.isFinite(score) ? `相关 · 评分 ${score}` : '相关'
  }
  return Number.isFinite(score) ? `不相关 · 评分 ${score}` : '不相关'
}

export function formatChunkLabel(pageNo: unknown, chunkIndex: unknown): string {
  const parts: string[] = []
  if (pageNo != null && Number.isFinite(Number(pageNo))) {
    parts.push(`第 ${Number(pageNo)} 页`)
  }
  if (chunkIndex != null && Number.isFinite(Number(chunkIndex))) {
    parts.push(`片段 #${Number(chunkIndex) + 1}`)
  }
  return parts.join(' · ')
}

export function traceSourceLabel(source?: string | null): string {
  const value = (source || '').trim().toLowerCase()
  if (value === 'lightrag' || value === 'graph') {
    return '图检索'
  }
  return '向量检索'
}

export function tracePathTypeLabel(kbType?: string | null): string {
  return kbType === 'lightrag' ? '图检索' : '向量检索'
}

export function formatMergePhaseLine(item: AgentTraceEvent): string {
  const meta = item.merge_meta
  if (!meta) {
    return ''
  }
  const pre = meta.pre_merge_total ?? pathRecallTotal(item)
  const post = meta.post_merge_total ?? item.total ?? 0
  const phases = item.merge_phases ?? meta.merge_phases ?? []
  const steps: string[] = []
  for (const phase of phases) {
    if (phase.phase === 'reserve_per_kb' && phase.count) {
      steps.push(`每库保底 ${phase.count}`)
    } else if (phase.phase === 'type_floor' && phase.count) {
      steps.push(`类型保底 ${phase.count}`)
    } else if (phase.phase === 'fill_by_merge_score' && phase.count) {
      steps.push(`按合并分补齐 ${phase.count}`)
    } else if (phase.phase === 'dedupe') {
      const dropped = phase.dropped ?? 0
      steps.push(dropped > 0 ? `去重 -${dropped}` : '去重')
    }
  }
  const mid = steps.length ? ` → ${steps.join(' → ')}` : ' → 公平合并'
  return `${pre} 条${mid} → ${post} 条`
}

/** 自动公平合并的策略说明（通用） */
export function formatMergeFairStrategyText(): string {
  return (
    '对各路候选在各自知识库内将原始检索分归一化为合并分（0～1），避免图库与向量库分数尺度不同导致偏斜。' +
    '随后分阶段选取：① 每个有命中的知识库至少保留 1 条；② 向量路与图路均命中时，每类型至少保留约合并 Top K 的 30%（至少 1 条）；' +
    '③ 按合并分从高到低补齐至「合并最终 Top K」；④ 去除同文档内高度重叠的重复片段。'
  )
}

/** 本轮回放：合并各阶段的具体数字 */
export function formatMergePhaseSteps(item: AgentTraceEvent): string[] {
  const meta = item.merge_meta
  if (!meta) {
    return []
  }
  const lines: string[] = []
  const pre = meta.pre_merge_total ?? pathRecallTotal(item)
  const mergeTopK = meta.merge_top_k ?? item.merge_top_k ?? item.top_k
  if (mergeTopK != null) {
    lines.push(`合并上限 ${mergeTopK} 条（对话设置中的「合并最终 Top K」）`)
  }
  lines.push(`候选池 ${pre} 条（图检索 + 向量检索召回之和）`)

  const phases = item.merge_phases ?? meta.merge_phases ?? []
  for (const phase of phases) {
    if (phase.phase === 'reserve_per_kb' && phase.count) {
      lines.push(`① 每库保底：先保留 ${phase.count} 条（每个知识库取合并分最高的 1 条）`)
    } else if (phase.phase === 'type_floor' && phase.count) {
      const floor = phase.floor ?? 1
      lines.push(`② 类型保底：再补 ${phase.count} 条（向量路与图路每类至少 ${floor} 条）`)
    } else if (phase.phase === 'fill_by_merge_score' && phase.count) {
      lines.push(`③ 按合并分补齐：再纳入 ${phase.count} 条（直至达到合并上限）`)
    } else if (phase.phase === 'dedupe') {
      const dropped = phase.dropped ?? 0
      if (dropped > 0) {
        lines.push(`④ 重叠去重：移除 ${dropped} 条同文档高度相似片段，剩 ${phase.count ?? meta.post_merge_total} 条`)
      }
    }
  }

  if (phases.length === 1 && phases[0]?.phase === 'dedupe' && pre > 0) {
    lines.push('① 单库检索：按合并分排序后直接截取至合并上限')
  }

  const breakdown = meta.type_breakdown
  const post = meta.post_merge_total ?? item.total ?? 0
  if (breakdown) {
    const parts: string[] = []
    if (breakdown.classic != null && breakdown.classic > 0) {
      parts.push(`向量 ${breakdown.classic}`)
    }
    if (breakdown.lightrag != null && breakdown.lightrag > 0) {
      parts.push(`图 ${breakdown.lightrag}`)
    }
    if (parts.length) {
      lines.push(`最终写入上下文 ${post} 条（${parts.join(' + ')}）`)
    } else {
      lines.push(`最终写入上下文 ${post} 条`)
    }
  }

  return lines
}
