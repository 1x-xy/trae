import { defineConfig } from 'vite'
import vue from '@vitejs/plugin-vue'

// 前端开发服务器：5173；通过代理把 /api 与 /static 转发到 FastAPI(8000)
export default defineConfig({
  plugins: [vue()],
  server: {
    host: '0.0.0.0', // 监听所有网卡，允许局域网手机/其他电脑访问
    port: 5173,
    strictPort: true, // 端口被占用时直接报错，避免端口漂移导致地址失效
    allowedHosts: true, // 允许通过内网穿透域名（如 xxx.trycloudflare.com）访问
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true
      },
      '/static': {
        target: 'http://localhost:8000',
        changeOrigin: true
      }
    }
  }
})
