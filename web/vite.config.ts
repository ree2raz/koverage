import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";

// Dev proxy: the SPA calls same-origin paths; Vite forwards them to the gateway,
// so there's no CORS dance and the prod build can sit behind one reverse proxy.
const GATEWAY = process.env.VITE_GATEWAY_URL || "http://localhost:8000";

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    port: 5173,
    proxy: {
      "/chat": { target: GATEWAY, changeOrigin: true },
      "/models": { target: GATEWAY, changeOrigin: true },
      "/conversations": { target: GATEWAY, changeOrigin: true },
      "/api": { target: GATEWAY, changeOrigin: true },
    },
  },
});
