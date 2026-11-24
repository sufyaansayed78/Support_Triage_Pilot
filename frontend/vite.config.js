import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";

// In dev the UI runs on :5173 and proxies API calls to the FastAPI app on :8000,
// so the browser only ever talks to one origin (no CORS needed).
// Override the target with: VITE_PROXY_TARGET=http://host:port npm run dev
const target = process.env.VITE_PROXY_TARGET || "http://localhost:8000";

export default defineConfig({
  plugins: [react()],
  server: {
    port: 5173,
    proxy: {
      "/v1": { target, changeOrigin: true },
      "/healthz": { target, changeOrigin: true },
    },
  },
});
