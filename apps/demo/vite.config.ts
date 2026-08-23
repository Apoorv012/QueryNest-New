import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'
import { resolve } from 'path'

const rootDir = import.meta.dirname

// Two static pages, no router dependency: index.html is the landing page,
// demo.html is the live search demo. VITE_API_BASE points at the deployed
// lite public backend (core.api.public_main).
export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5174,
    proxy: {
      '/api': {
        // 127.0.0.1, not 'localhost' — see tools/dev-dashboard/vite.config.ts.
        target: 'http://127.0.0.1:8001',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
  build: {
    rollupOptions: {
      input: {
        main: resolve(rootDir, 'index.html'),
        demo: resolve(rootDir, 'demo/index.html'),
      },
    },
  },
})
