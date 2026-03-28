import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'

const apiProxy = {
  '/api': {
    target: 'http://localhost:8000',
    changeOrigin: true,
  },
  '/ws': {
    target: 'ws://localhost:8000',
    ws: true,
  },
} as const

export default defineConfig({
  plugins: [react()],
  server: {
    port: 3000,
    proxy: { ...apiProxy },
  },
  // run-all.ps1 / preview на :4173 — без этого /api уходит в статик и логин ломается
  preview: {
    proxy: { ...apiProxy },
  },
})
