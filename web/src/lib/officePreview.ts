/** 浏览器内预览 Office 类文件：docx→HTML，表格类→HTML 表格（非浏览器原生能力） */

export type SpreadsheetSheet = {
  name: string
  rows: string[][]
}

export type ParsedSpreadsheet = {
  sheets: SpreadsheetSheet[]
  isCsv: boolean
}

export const SPREADSHEET_INITIAL_ROWS = 50
export const SPREADSHEET_ROW_BATCH = 50

export function escapeHtml(s: string): string {
  return s
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;')
}

export async function docxBlobToHtml(blob: Blob): Promise<string> {
  const mammoth = await import('mammoth')
  const arrayBuffer = await blob.arrayBuffer()
  const result = await mammoth.convertToHtml(
    { arrayBuffer },
    {
      convertImage: mammoth.images.imgElement((image) =>
        image.read('base64').then((imageBuffer) => ({
          src: `data:${image.contentType};base64,${imageBuffer}`,
        })),
      ),
    },
  )
  return result.value
}

const MAX_SHEET_ROWS = 400

function normalizeSheetRows(data: (string | number | boolean | null)[][]): string[][] {
  let maxCols = 0
  for (const row of data) {
    maxCols = Math.max(maxCols, row.length)
  }
  if (maxCols === 0) {
    maxCols = 1
  }
  return data.map((row) => {
    const cells: string[] = []
    for (let c = 0; c < maxCols; c += 1) {
      const cell = c < row.length ? row[c] : ''
      cells.push(String(cell ?? ''))
    }
    return cells
  })
}

/** 解析 Excel/CSV 为结构化行列（供 Vue 表格组件分批渲染） */
export async function parseSpreadsheetBlob(blob: Blob, fileName: string): Promise<ParsedSpreadsheet> {
  const ext = fileName.includes('.') ? fileName.split('.').pop()!.toLowerCase() : ''

  if (ext === 'csv') {
    const text = await blob.text()
    const XLSX = await import('xlsx')
    const workbook = XLSX.read(text, { type: 'string' })
    const sheet = workbook.Sheets[workbook.SheetNames[0] ?? '']
    if (!sheet) {
      return { sheets: [{ name: 'CSV', rows: [] }], isCsv: true }
    }
    const data = XLSX.utils.sheet_to_json<(string | number | boolean | null)[]>(sheet, {
      header: 1,
      defval: '',
      raw: false,
    }) as (string | number | boolean | null)[][]
    return { sheets: [{ name: 'CSV', rows: normalizeSheetRows(data) }], isCsv: true }
  }

  const XLSX = await import('xlsx')
  const arrayBuffer = await blob.arrayBuffer()
  const workbook = XLSX.read(arrayBuffer, { type: 'array' })

  const sheets: SpreadsheetSheet[] = []
  for (const name of workbook.SheetNames) {
    const sheet = workbook.Sheets[name]
    if (!sheet) {
      continue
    }
    const data = XLSX.utils.sheet_to_json<(string | number | boolean | null)[]>(sheet, {
      header: 1,
      defval: '',
      raw: false,
    }) as (string | number | boolean | null)[][]
    sheets.push({ name, rows: normalizeSheetRows(data) })
  }

  return { sheets: sheets.length ? sheets : [{ name: 'Sheet1', rows: [] }], isCsv: false }
}

/** @deprecated 大表请用 parseSpreadsheetBlob + SpreadsheetOriginalPreview */
export async function spreadsheetBlobToHtml(blob: Blob, fileName: string): Promise<string> {
  const parsed = await parseSpreadsheetBlob(blob, fileName)
  const ext = fileName.includes('.') ? fileName.split('.').pop()!.toLowerCase() : ''

  if (ext === 'csv' && parsed.sheets[0]) {
    const text = parsed.sheets[0].rows.map((row) => row.join(',')).join('\n')
    return `<pre class="csv-preview">${escapeHtml(text)}</pre>`
  }

  let html = ''
  for (const { name, rows } of parsed.sheets) {
    const limited = rows.slice(0, MAX_SHEET_ROWS)
    html += `<section class="sheet-section"><h4 class="sheet-title">${escapeHtml(name)}</h4>`
    if (limited.length === 0) {
      html += '<p class="sheet-empty">（空表）</p></section>'
      continue
    }
    html += '<div class="xlsx-table-wrap chunk-data-table-compact"><table class="xlsx-preview-table"><tbody>'
    for (const row of limited) {
      html += '<tr>'
      for (const cell of row) {
        html += `<td title="${escapeHtml(cell)}">${escapeHtml(cell)}</td>`
      }
      html += '</tr>'
    }
    html += '</tbody></table></div>'
    if (rows.length > MAX_SHEET_ROWS) {
      html += `<p class="sheet-truncated">仅展示前 ${MAX_SHEET_ROWS} 行，共 ${rows.length} 行</p>`
    }
    html += '</section>'
  }
  return html || '<p class="sheet-empty">无法读取工作表内容</p>'
}
