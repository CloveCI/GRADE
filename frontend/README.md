# GRADE frontend (GRADE Companion)

React 19 + Vite single-page app for uploading answer keys and sheets, reviewing graded regions, and downloading reports.
It calls the FastAPI backend in [`../backend`](../backend).

```bash
npm ci
npm run dev        # http://127.0.0.1:5173, proxies API routes to http://127.0.0.1:8000 (vite.config.js)
npm run lint
npm run build      # static output in dist/
```

Leave `VITE_API_URL` empty in development; set it only when the API runs on another host (see `.env.example`).
More detail: [`docs/services/frontend.md`](../docs/services/frontend.md).
