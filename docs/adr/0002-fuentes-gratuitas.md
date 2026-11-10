# ADR 0002: Solo fuentes gratuitas y sin saltar protecciones

**Estado**: aceptada (2026-10-19)

## Contexto
Presupuesto 0 para el primer mes. Se pidió usar FotMob, Opta y SofaScore, y cuotas de bet365 y Betano.

## Decisión
- FotMob (que muestra datos Opta), football-data.co.uk y Understat, con caché en disco y una petición cada 1,5 s.
- Cuotas de bet365 vía football-data.co.uk. Betano vía OddsPapi (clave gratuita, opcional) y, mientras tanto, por evaluación manual (`evaluar_cuota`).
- SofaScore descartado porque bloquea (403). **No se usan técnicas para esquivar protecciones anti-bots.**

## Consecuencias
- Si una fuente cambia su formato, falla solo esa tarea (registrada en `ingestion_run`).
- Los datos son para uso personal. Para monetizar habría que pasar a una fuente con licencia: el diseño (`ingest/` por fuente + `store.py`) lo permite añadiendo un adaptador.
