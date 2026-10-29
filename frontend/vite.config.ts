import { fileURLToPath, URL } from 'node:url'

import tailwindcss from '@tailwindcss/vite'
import vue from '@vitejs/plugin-vue'
import { defineConfig } from 'vite'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [vue(), vueDevTools(), tailwindcss()],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  server: {
    // The browser only talks to Vite; Vite forwards /api to FastAPI. Same origin, so no CORS.
    // 127.0.0.1 instead of localhost: Node may resolve localhost to IPv6 (::1),
    // while uvicorn listens on IPv4 only.
    proxy: {
      '/api': 'http://127.0.0.1:8000',
    },
  },
})
