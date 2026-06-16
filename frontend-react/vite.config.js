import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const API_TARGET = 'http://127.0.0.1:8000'

/** Dev proxy: browser calls same origin; Vite forwards to FastAPI. */
const proxyPaths = [
  '/api',
  '/health',
  '/upload/key',
  '/upload/sheet',
  '/upload/exam-bundle',
  '/evaluate',
  '/result',
  '/report',
  '/sheet',
  '/jobs',
]

function proxyEntry(path) {
  const opts = { target: API_TARGET, changeOrigin: true }
  // Handwritten OCR + LLM grading can take several minutes on multi-question exams.
  if (path === '/evaluate' || path === '/jobs') {
    opts.timeout = 600_000
    opts.proxyTimeout = 600_000
  }
  return [path, opts]
}

export default defineConfig({
  appType: 'spa',
  plugins: [react()],
  server: {
    proxy: Object.fromEntries(
      proxyPaths.map(proxyEntry),
    ),
  },
})
