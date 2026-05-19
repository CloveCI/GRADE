import { defineConfig } from "vite";
import react from "@vitejs/plugin-react-swc";
import path from "path";
import { componentTagger } from "lovable-tagger";

export default defineConfig(({ mode }) => ({
  server: {
    host: "0.0.0.0",
    port: 5173,
    strictPort: true,
    hmr: {
      overlay: false,
    },
    proxy: {
      "/health": "http://127.0.0.1:8000",
      "/api": "http://127.0.0.1:8000",
      "/upload/key": "http://127.0.0.1:8000",
      "/upload/sheet": "http://127.0.0.1:8000",
      "/upload/exam-bundle": "http://127.0.0.1:8000",
      "/evaluate": {
        target: "http://127.0.0.1:8000",
        changeOrigin: true,
        bypass(req) {
          if (req.method === "GET" || req.method === "HEAD") {
            return "/index.html";
          }
        },
      },
      // Trailing slash so "/results" and "/sheets" (React routes) are not prefix-matched.
      "/result/": "http://127.0.0.1:8000",
      "/report/": "http://127.0.0.1:8000",
      "/sheet/": "http://127.0.0.1:8000",
    },
  },
  plugins: [react(), mode === "development" && componentTagger()].filter(Boolean),
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
    dedupe: ["react", "react-dom", "react/jsx-runtime", "react/jsx-dev-runtime", "@tanstack/react-query", "@tanstack/query-core"],
  },
}));
