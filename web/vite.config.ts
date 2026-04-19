import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
    // During local dev we proxy /api/* to the central app on 127.0.0.1:8090
    proxy: {
      "/api": {
        target: "http://127.0.0.1:8090",
        changeOrigin: false,
        secure: false,
      },
    },
  },
  build: {
    outDir: "dist",
    sourcemap: true,
  },
});
