import * as pdfjs from 'pdfjs-dist'

let configured = false

/** 使用 public/ 下固定文件名，避免 prod 资源 hash 与 nginx SPA 回退导致 worker 加载失败 */
export function setupPdfjsWorker() {
  if (configured) {
    return
  }
  const base = import.meta.env.BASE_URL || '/'
  pdfjs.GlobalWorkerOptions.workerSrc = `${base}pdf.worker.min.mjs`
  configured = true
}

export { pdfjs }
