# Panel web

Interfaz visual de App Apuestas (Next.js + TypeScript + Tailwind, gráficas con ECharts). Todo el texto está en español y las horas en hora de Lima.

Consume la API FastAPI del proyecto desde el navegador. Cómo arrancarlo: ver la sección «Panel web» del [README principal](../README.md).

## Estructura

- `src/app/`: una carpeta por página (`/`, `/partidos`, `/partidos/[id]`, `/evaluar`, `/rendimiento`, `/datos`).
- `src/components/`: la vista de cada página y las piezas comunes (`ui.tsx`, `Chart.tsx` con ECharts, `PenMark.tsx`).
- `src/lib/`: cliente de la API (`api.ts`, con SWR), tipos de las respuestas (`types.ts`), formato de cifras y fechas (`format.ts`) y nombres de mercados (`markets.ts`).

## Comandos

```bash
npm run dev     # desarrollo en http://localhost:3000
npm run build   # compilación de producción
npm start       # sirve la compilación
npm run lint
```
