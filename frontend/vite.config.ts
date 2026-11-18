import react from '@vitejs/plugin-react'
import { defineConfig } from 'vitest/config'

// Rotas da API (o front usa rotas com "#", então não há conflito com estes caminhos).
const API = ['auth', 'usuarios', 'clientes', 'enderecos', 'produtos', 'estoque', 'pedidos', 'relatorios', 'sistema', 'health']

export default defineConfig({
  plugins: [react()],
  // O build vai direto para a pasta que o backend serve.
  build: { outDir: '../app/web', emptyOutDir: true, sourcemap: false, chunkSizeWarningLimit: 900 },
  server: {
    port: 5173,
    // Em desenvolvimento (npm run dev) as chamadas vão para o backend local, sem CORS.
    proxy: Object.fromEntries(API.map((p) => [`/${p}`, { target: 'http://127.0.0.1:8000', changeOrigin: false }])),
  },
  test: {
    environment: 'jsdom',
    setupFiles: ['./src/test/setup.ts'],
    globals: true,
    css: false,
    restoreMocks: true,
  },
})
