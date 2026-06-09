import type { KnowledgeChunk, KnowledgeDocument } from '../api/knowledge-base'
import { knowledgeBaseApi } from '../api/knowledge-base'
import {
  buildDocxPageAnchorTexts,
  chunkOriginalScrollProbe,
  type DocxContentBlock,
  findDocxBlockForChunk,
  docxHighlightTextForBlock,
  resolveChunkWordPage,
} from './docxContentDisplay'
import { mineruBlockPlainText } from './mineruContentDisplay'

const OFFICE_PREVIEW_EXTS = new Set(['doc', 'docx', 'pdf', 'xlsx', 'xlsm', 'xls', 'csv'])

export function canShowOfficeOriginalPreview(fileExt: string | null | undefined) {
  return OFFICE_PREVIEW_EXTS.has(String(fileExt || '').toLowerCase())
}

function normalizeContentListItem(item: unknown, index: number): DocxContentBlock {
  if (!item || typeof item !== 'object') {
    return { block_index: index, text: '' }
  }
  const row = item as Record<string, unknown>
  let text = ''
  if (typeof row.text === 'string' && row.text.trim()) {
    text = row.text.trim()
  } else if (typeof row.image_ocr_text === 'string' && row.image_ocr_text.trim()) {
    text = row.image_ocr_text.trim()
  } else {
    text = mineruBlockPlainText(row).trim()
  }
  const pageIdx = typeof row.page_idx === 'number' ? row.page_idx : undefined
  return {
    block_index: typeof row.block_index === 'number' ? row.block_index : index,
    type: String(row.type || row.block || 'text'),
    text,
    page_idx: pageIdx,
    page_no: typeof row.page_no === 'number' ? row.page_no : pageIdx != null ? pageIdx + 1 : undefined,
    heading_path: typeof row.heading_path === 'string' ? row.heading_path : null,
  }
}

export async function loadDocumentContentListBlocks(
  kbId: number,
  document: KnowledgeDocument,
): Promise<DocxContentBlock[]> {
  const ext = String(document.file_ext || '').toLowerCase()
  if (ext !== 'docx' && ext !== 'doc') {
    return []
  }
  const backend = String(document.metadata?.parser_backend || '')
  try {
    const raw =
      backend && backend !== 'mineru' && backend !== 'opendataloader'
        ? await knowledgeBaseApi.getDocumentDocxContentListText(kbId, document.id)
        : await knowledgeBaseApi.getDocumentMineruContentListText(kbId, document.id)
    const parsed = JSON.parse(raw) as unknown[]
    if (!Array.isArray(parsed)) {
      return []
    }
    return parsed.map(normalizeContentListItem)
  } catch {
    return []
  }
}

/** 去掉 OCR / HTML 噪声，保留可在 Word 原文中匹配的 prose 片段。 */
export function stripMarkupForHighlightProbe(text: string): string {
  const lines = text
    .split('\n')
    .map((line) => line.trim())
    .filter(Boolean)
  const proseLines = lines.filter(
    (line) =>
      !line.startsWith('<') &&
      !line.includes('<table') &&
      !line.startsWith('##') &&
      !line.includes('$$') &&
      line.length >= 4,
  )
  const merged = (proseLines.length ? proseLines.join(' ') : text.replace(/<[^>]+>/g, ' '))
    .replace(/\s+/g, ' ')
    .trim()
  if (merged.length <= 160) {
    return merged
  }
  const sentence = merged.match(/[^。！？；]{8,160}[。！？；]?/)
  return (sentence?.[0] || merged.slice(0, 120)).trim()
}

export function resolveChunkHighlightForOriginalPreview(
  chunk: KnowledgeChunk,
  blocks: DocxContentBlock[],
): {
  highlight: string | null
  syncPage: number | null
  pageAnchors: Record<number, string> | null
} {
  const pageAnchors = blocks.length ? buildDocxPageAnchorTexts(blocks) : null
  const syncPage = blocks.length ? resolveChunkWordPage(chunk, blocks) : chunk.page_no ?? null
  const meta = chunk.metadata
  const blockIdx = findDocxBlockForChunk(chunk, blocks)

  if (blockIdx != null) {
    const fromBlock = docxHighlightTextForBlock(blocks, blockIdx)
    if (fromBlock) {
      return {
        highlight: stripMarkupForHighlightProbe(fromBlock),
        syncPage,
        pageAnchors,
      }
    }
  }

  if (meta?.block === 'image') {
    const heading = chunk.heading_path?.split(' / ').pop()?.replace(/\*\*/g, '').trim()
    const probe = chunkOriginalScrollProbe(chunk, blocks)
    const cleaned = probe ? stripMarkupForHighlightProbe(probe) : null
    if (cleaned && cleaned.length >= 8) {
      return { highlight: cleaned, syncPage, pageAnchors }
    }
    if (heading && heading.length >= 4) {
      return { highlight: heading.length > 80 ? heading.slice(0, 80) : heading, syncPage, pageAnchors }
    }
  }

  const probe = chunkOriginalScrollProbe(chunk, blocks)
  return {
    highlight: probe ? stripMarkupForHighlightProbe(probe) : null,
    syncPage,
    pageAnchors,
  }
}
