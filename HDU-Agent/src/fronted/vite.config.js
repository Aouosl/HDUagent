import { defineConfig } from 'vite';

export default defineConfig({
  root: '.',
  base: '/',
  server: {
    port: 5173,
    proxy: {
      '/api': 'http://127.0.0.1:8000',
      '/ws': {
        target: 'ws://127.0.0.1:8000',
        ws: true
      }
    }
  },
  build: {
    outDir: 'dist',
    assetsDir: 'assets',
    rollupOptions: {
      input: {
        main: 'index.html',
        landing: 'landing.html',
        login: 'login.html',
        register: 'register.html'
      }
    }
  },
  // CDN 渚濊禆淇濇寔澶栭儴鍖栵紝涓嶆墦鍖?
  resolve: {
    alias: {}
  }
});
