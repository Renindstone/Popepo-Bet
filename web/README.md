# Web dashboard

**English** · [Español](README.es.md)

Visual interface of Popepo-Bet (Next.js + TypeScript + Tailwind, charts with ECharts). In Spanish or English (ES / EN switch in the header), with times shown in Lima time.

Every text carries both versions where it's used: `tr("Hoy", "Today")` (`src/lib/i18n.tsx`), also in `format.ts` and `markets.ts`. What the API sends arrives already translated (the dashboard sends `Accept-Language`).

It consumes the project's FastAPI API from the browser. How to start it: see the "Web dashboard" section of the [main README](../README.md).

## Structure

- `src/app/`: one folder per page (`/`, `/partidos`, `/partidos/[id]`, `/evaluar`, `/rendimiento`, `/datos`).
- `src/components/`: each page's view and the shared pieces (`ui.tsx`, `Chart.tsx` with ECharts, `PenMark.tsx`).
- `src/lib/`: API client (`api.ts`, with SWR), response types (`types.ts`), number and date formatting (`format.ts`) and market names (`markets.ts`).

## Commands

```bash
npm run dev     # development at http://localhost:3000
npm run build   # production build
npm start       # serves the build
npm run lint
```
