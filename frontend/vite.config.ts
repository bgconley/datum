import path from 'path'
import { defineConfig } from 'vite'
import react from '@vitejs/plugin-react'
import tailwindcss from '@tailwindcss/vite'

export default defineConfig({
  plugins: [react(), tailwindcss()],
  resolve: {
    extensions: ['.ts', '.tsx', '.js', '.jsx', '.mjs', '.json'],
    alias: {
      '@': path.resolve(__dirname, './src'),
    },
  },
  build: {
    // Heavy editor/diagram vendor chunks are lazy-loaded by route/view mode.
    // Keep warning focus on initial-entry regressions rather than optional vendors.
    chunkSizeWarningLimit: 2500,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (
            id.includes('node_modules/@codemirror') ||
            id.includes('node_modules/codemirror') ||
            id.includes('node_modules/@uiw/react-codemirror')
          ) {
            return 'codemirror-vendor'
          }

          if (
            id.includes('node_modules/react-diff-view') ||
            id.includes('node_modules/gitdiff-parser')
          ) {
            return 'diff-vendor'
          }

          if (id.includes('node_modules/react-pdf') || id.includes('node_modules/pdfjs-dist')) {
            return 'pdf-vendor'
          }

          if (id.includes('node_modules/mermaid') || id.includes('node_modules/katex')) {
            return 'mermaid-vendor'
          }

          if (
            id.includes('node_modules/cytoscape') ||
            id.includes('node_modules/layout-base') ||
            id.includes('node_modules/cose-base') ||
            id.includes('node_modules/cytoscape-cose-bilkent')
          ) {
            return 'graph-vendor'
          }

          return undefined
        },
      },
    },
  },
  server: {
    port: 3000,
    proxy: {
      '/api': {
        target: 'http://localhost:8001',
        changeOrigin: true,
      },
      '/ws': {
        target: 'ws://localhost:8001',
        ws: true,
      },
    },
  },
})
