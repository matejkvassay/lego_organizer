# Frontend

React + TypeScript + Vite + Tailwind CSS (v4). No router or state library: a ~25-line hash router (`src/route.ts`) and plain `useState`.

```
npm install
npm run dev     # http://localhost:5173, proxies /api and /auth to the backend on :8000
npm run build   # outputs dist/, which the backend serves in production
```

See the [architecture doc](../docs/architecture.md) for how it fits together.
