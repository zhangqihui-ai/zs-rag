import { cpSync, existsSync } from 'node:fs'
import { resolve } from 'node:path'
import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

const pdfWorkerSource = resolve('node_modules/pdfjs-dist/build/pdf.worker.min.mjs')
const pdfWorkerPublic = resolve('public/pdf.worker.min.mjs')

function copyPdfWorker() {
  if (!existsSync(pdfWorkerSource)) {
    return
  }
  cpSync(pdfWorkerSource, pdfWorkerPublic)
}

copyPdfWorker()

const devProxyTarget = process.env.VITE_DEV_PROXY_TARGET ?? 'http://backend:8000'

/** 浏览器打开/刷新/克隆标签走 SPA；带 X-ZS-RAG-API 或非 GET 才转发后端 */
function spaAwareProxy() {
  return {
    target: devProxyTarget,
    changeOrigin: true,
    bypass(req) {
      const method = (req.method ?? 'GET').toUpperCase()
      const isApiClient = String(req.headers['x-zs-rag-api'] ?? '') === '1'
      const accept = String(req.headers.accept ?? '').toLowerCase()
      const wantsJson = accept.includes('application/json')
      if (method === 'GET' && !isApiClient && !wantsJson) {
        return '/index.html'
      }
    },
  }
}

export default defineConfig({
  plugins: [
    vue(),
    {
      name: 'copy-pdf-worker',
      buildStart() {
        copyPdfWorker()
      },
    },
  ],
  optimizeDeps: {
    include: ['mammoth', 'xlsx', 'pdfjs-dist', 'marked'],
  },
  server: {
    port: 5173,
    host: '0.0.0.0',
    watch: {
      usePolling: true,
      interval: 300,
    },
    proxy: {
      '/auth': { ...spaAwareProxy(), timeout: 900_000, proxyTimeout: 900_000 },
      '/health': spaAwareProxy(),
      '/system': { ...spaAwareProxy(), timeout: 900_000, proxyTimeout: 900_000 },
      '/enterprise-spaces': { ...spaAwareProxy(), timeout: 900_000, proxyTimeout: 900_000 },
      '/users': { ...spaAwareProxy(), timeout: 900_000, proxyTimeout: 900_000 },
      '/knowledge-bases': { ...spaAwareProxy(), timeout: 900_000, proxyTimeout: 900_000 },
      '/platform-audit': { ...spaAwareProxy(), timeout: 900_000, proxyTimeout: 900_000 },
      '/api': { ...spaAwareProxy(), timeout: 900_000, proxyTimeout: 900_000 },
    },
  },
  define: {
    'import.meta.env.VITE_API_BASE_URL': JSON.stringify(process.env.VITE_API_BASE_URL ?? ''),
  },
})
