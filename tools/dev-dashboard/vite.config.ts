import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        // 127.0.0.1, not 'localhost'. On Windows 'localhost' resolves to
        // IPv6 ::1 first while uvicorn binds IPv4-only, so every proxied
        // request stalls ~2s on the failed IPv6 attempt before falling back.
        // Measured: 2083ms via localhost vs 16ms via 127.0.0.1.
        target: 'http://127.0.0.1:8000',
        rewrite: (path) => path.replace(/^\/api/, ''),
      },
    },
  },
})
