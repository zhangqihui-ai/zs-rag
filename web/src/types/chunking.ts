export type ChunkingMode = 'general' | 'parent_child'

export interface ChunkingGeneralForm {
  /** 分段用分隔，支持 \\n 转义为换行等 */
  delimiter: string
  max_length: number
  overlap: number
  collapse_whitespace: boolean
}

export interface ChunkingParentChildForm {
  parent_mode: 'paragraph' | 'full_document'
  parent_delimiter: string
  parent_max_length: number
  child_delimiter: string
  child_max_length: number
  child_overlap: number
  collapse_whitespace: boolean
}

/** 与后端 knowledge_base.config.chunking 对齐 */
export interface ChunkingConfigStored {
  mode: ChunkingMode
  general: ChunkingGeneralForm
  parent_child: ChunkingParentChildForm
}

export const DEFAULT_CHUNKING: ChunkingConfigStored = {
  mode: 'general',
  general: {
    delimiter: '\\n\\n',
    max_length: 1024,
    overlap: 50,
    collapse_whitespace: true,
  },
  parent_child: {
    parent_mode: 'paragraph',
    parent_delimiter: '\\n\\n',
    parent_max_length: 1024,
    child_delimiter: '\\n',
    child_max_length: 512,
    child_overlap: 50,
    collapse_whitespace: true,
  },
}

export function loadChunkingConfig(
  config: Record<string, unknown> | null | undefined,
  defaultChunkSize: number,
  defaultChunkOverlap: number,
): ChunkingConfigStored {
  const raw = config?.chunking as Partial<ChunkingConfigStored> | undefined
  if (!raw || typeof raw !== 'object') {
    return {
      ...DEFAULT_CHUNKING,
      general: {
        ...DEFAULT_CHUNKING.general,
        max_length: defaultChunkSize,
        overlap: defaultChunkOverlap,
      },
    }
  }
  const gen = { ...DEFAULT_CHUNKING.general, ...raw.general }
  const pc = { ...DEFAULT_CHUNKING.parent_child, ...raw.parent_child }
  const normalizeDelimiter = (value: unknown, fallback: string) => {
    if (typeof value !== 'string') {
      return fallback
    }
    // 兼容历史：若后端/旧前端存了真实换行，转成可见的 \\n 形式
    return value.replace(/\r\n/g, '\n').replace(/\n/g, '\\n').replace(/\t/g, '\\t')
  }
  return {
    mode: raw.mode === 'parent_child' ? 'parent_child' : 'general',
    general: {
      delimiter: normalizeDelimiter(gen.delimiter, DEFAULT_CHUNKING.general.delimiter),
      max_length: gen.max_length ?? defaultChunkSize,
      overlap: gen.overlap ?? defaultChunkOverlap,
      collapse_whitespace:
        typeof gen.collapse_whitespace === 'boolean' ? gen.collapse_whitespace : DEFAULT_CHUNKING.general.collapse_whitespace,
    },
    parent_child: {
      parent_mode: pc.parent_mode === 'full_document' ? 'full_document' : 'paragraph',
      parent_delimiter: normalizeDelimiter(pc.parent_delimiter, DEFAULT_CHUNKING.parent_child.parent_delimiter),
      parent_max_length: pc.parent_max_length ?? DEFAULT_CHUNKING.parent_child.parent_max_length,
      child_delimiter: normalizeDelimiter(pc.child_delimiter, DEFAULT_CHUNKING.parent_child.child_delimiter),
      child_max_length: pc.child_max_length ?? DEFAULT_CHUNKING.parent_child.child_max_length,
      child_overlap: pc.child_overlap ?? DEFAULT_CHUNKING.parent_child.child_overlap,
      collapse_whitespace:
        typeof pc.collapse_whitespace === 'boolean' ? pc.collapse_whitespace : DEFAULT_CHUNKING.parent_child.collapse_whitespace,
    },
  }
}

export function toStoredConfig(form: {
  mode: ChunkingMode
  general: ChunkingGeneralForm
  parent_child: ChunkingParentChildForm
}): ChunkingConfigStored {
  return {
    mode: form.mode,
    general: { ...form.general },
    parent_child: { ...form.parent_child },
  }
}
