import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

const api = "http://127.0.0.1:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    host: true,
    port: 5173,
    proxy: {
      "/api": { target: api, changeOrigin: true },
      "/placeholders": { target: api, changeOrigin: true },
    },
  },
  preview: {
    host: true,
    port: 4173,
    proxy: {
      "/api": { target: api, changeOrigin: true },
      "/placeholders": { target: api, changeOrigin: true },
    },
  },
});
