/** 浏览器内预览 Office 类文件：docx→HTML，表格类→HTML 表格（非浏览器原生能力） */

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

export async function spreadsheetBlobToHtml(blob: Blob, fileName: string): Promise<string> {
  const ext = fileName.includes('.') ? fileName.split('.').pop()!.toLowerCase() : ''

  if (ext === 'csv') {
    const text = await blob.text()
    return `<pre class="csv-preview">${escapeHtml(text)}</pre>`
  }

  const XLSX = await import('xlsx')
  const arrayBuffer = await blob.arrayBuffer()
  const workbook = XLSX.read(arrayBuffer, { type: 'array' })

  let html = ''
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

    const rows = data.slice(0, MAX_SHEET_ROWS)
    let maxCols = 0
    for (const r of rows) {
      maxCols = Math.max(maxCols, r.length)
    }
    if (maxCols === 0) {
      maxCols = 1
    }

    html += `<section class="sheet-section"><h4 class="sheet-title">${escapeHtml(name)}</h4>`
    if (rows.length === 0) {
      html += '<p class="sheet-empty">（空表）</p></section>'
      continue
    }
    html += '<div class="xlsx-table-wrap"><table class="xlsx-preview-table"><tbody>'
    for (const row of rows) {
      html += '<tr>'
      for (let c = 0; c < maxCols; c += 1) {
        const cell = c < row.length ? row[c] : ''
        html += `<td>${escapeHtml(String(cell ?? ''))}</td>`
      }
      html += '</tr>'
    }
    html += '</tbody></table></div>'
    if (data.length > MAX_SHEET_ROWS) {
      html += `<p class="sheet-truncated">仅展示前 ${MAX_SHEET_ROWS} 行，共 ${data.length} 行</p>`
    }
    html += '</section>'
  }
  return html || '<p class="sheet-empty">无法读取工作表内容</p>'
}
