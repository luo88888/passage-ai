import { fileURLToPath, URL } from 'node:url'

import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'
import vueDevTools from 'vite-plugin-vue-devtools'

// https://vite.dev/config/
export default defineConfig({
  plugins: [
    vue(),
    vueDevTools(),
  ],
  resolve: {
    alias: {
      '@': fileURLToPath(new URL('./src', import.meta.url)),
    },
  },
  // 开发代理：前端请求改为同源 /api 后，由 Vite 转发到后端 8567，保持本地开发体验不变
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8567',
        changeOrigin: true,
      },
    },
  },
})
