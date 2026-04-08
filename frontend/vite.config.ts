import { defineConfig, splitVendorChunkPlugin } from 'vite';
import react from '@vitejs/plugin-react';

export default defineConfig({
  plugins: [react(), splitVendorChunkPlugin()],
  server: {
    port: 3000,
    host: true,
  },
  build: {
    chunkSizeWarningLimit: 650,
    rollupOptions: {
      output: {
        manualChunks(id) {
          if (id.includes('node_modules')) {
            if (id.includes('pixi.js') || id.includes('@pixi')) {
              return 'pixi-vendor';
            }
            if (id.includes('react') || id.includes('scheduler')) {
              return 'react-vendor';
            }
            if (id.includes('zustand')) {
              return 'state-vendor';
            }
            return 'vendor';
          }

          if (id.includes('/src/engine/') || id.includes('/src/components/agents/')) {
            return 'office-renderer';
          }

          return undefined;
        },
      },
    },
  },
  resolve: {
    alias: {
      '@': '/src',
    },
  },
  optimizeDeps: {
    include: ['pixi.js', '@pixi/react'],
  },
});
