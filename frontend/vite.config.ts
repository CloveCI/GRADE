// @lovable.dev/vite-tanstack-config already includes the following — do NOT add them manually
// or the app will break with duplicate plugins:
//   - tanstackStart, viteReact, tailwindcss, tsConfigPaths, cloudflare (build-only),
//     componentTagger (dev-only), VITE_* env injection, @ path alias, React/TanStack dedupe,
//     error logger plugins, and sandbox detection (port/host/strictPort).
import { defineConfig } from "@lovable.dev/vite-tanstack-config";

const FASTAPI = "http://127.0.0.1:8000";
const proxy: Record<string, unknown> = {
  "/api": FASTAPI,
  "/upload": FASTAPI,
  "/health": FASTAPI,
  "/result/": FASTAPI,
  "/report/": FASTAPI,
  "/sheet/": FASTAPI,
  "/evaluate": {
    target: FASTAPI,
    changeOrigin: true,
    bypass(req) {
      if (req.method === "GET" || req.method === "HEAD") {
        return "/index.html";
      }
    },
  },
};

export default defineConfig({
  tanstackStart: {
    server: { entry: "server" },
  },
  vite: {
    server: { proxy },
    preview: { proxy },
  },
});
