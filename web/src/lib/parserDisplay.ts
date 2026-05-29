import type { KnowledgeBase, KnowledgeDocument } from '../api/knowledge-base'

const PARSER_ENGINE_LABELS: Record<string, string> = {
  opendataloader: 'OpenDataLoader',
  mineru: 'MinerU',
  docling: 'Docling',
  pypdf: 'pypdf',
  pypdf_fallback: 'pypdf',
  'python-docx': 'python-docx',
  html_table: 'HTML 表格',
  tsv: 'TSV',
  standard: 'CSV',
  native: '文本',
}

export function parserEngineLabel(engine: string | null | undefined, fallback = false): string {
  const key = (engine || '').trim().toLowerCase()
  if (!key) return '—'
  const base = PARSER_ENGINE_LABELS[key] || key
  return fallback ? `${base}（降级）` : base
}

function configuredPdfEngine(kb: KnowledgeBase | null | undefined): string | null {
  const cfg = kb?.config
  if (!cfg || typeof cfg !== 'object') return null
  const parsers = cfg.parsers as Record<string, { engine?: string }> | undefined
  const fromStructured = parsers?.pdf?.engine
  if (typeof fromStructured === 'string' && fromStructured.trim()) {
    return fromStructured.trim().toLowerCase()
  }
  const legacy = cfg.pdf_parser
  if (typeof legacy === 'string' && legacy.trim()) {
    return legacy.trim().toLowerCase()
  }
  return null
}

function configuredEngineForExt(kb: KnowledgeBase | null | undefined, ext: string | null | undefined): string | null {
  const e = (ext || '').toLowerCase()
  const cfg = kb?.config
  if (!cfg || typeof cfg !== 'object') return null
  const parsers = cfg.parsers as Record<string, { engine?: string }> | undefined
  if (!parsers) return null
  if (e === 'pdf') return configuredPdfEngine(kb)
  if (e === 'docx' || e === 'doc') return parsers.docx?.engine?.trim().toLowerCase() || null
  if (e === 'xlsx' || e === 'xlsm' || e === 'xls') return parsers.excel?.engine?.trim().toLowerCase() || null
  if (e === 'csv') return parsers.csv?.engine?.trim().toLowerCase() || null
  if (e === 'txt' || e === 'md') return parsers.text?.engine?.trim().toLowerCase() || null
  return null
}

/** 文档列表「解析器」列：优先展示实际 backend，未解析时展示知识库配置。 */
export function documentParserDisplay(
  document: KnowledgeDocument,
  kb?: KnowledgeBase | null,
): string {
  if (document.parser_engine_label) {
    return document.parser_engine_label
  }
  const meta = document.metadata
  const backend = typeof meta?.parser_backend === 'string' ? meta.parser_backend : null
  if (backend) {
    return parserEngineLabel(backend, meta?.parser_fallback === true)
  }
  const configured = configuredEngineForExt(kb, document.file_ext || document.parser_type)
  if (configured) {
    const pending =
      document.status === 'uploaded' ||
      document.status === 'failed' ||
      document.chunk_count === 0
    return pending ? `${parserEngineLabel(configured)}（待解析）` : parserEngineLabel(configured)
  }
  return (document.parser_type || '—').toUpperCase()
}
