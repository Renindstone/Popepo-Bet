import { Tag } from "@/components/ui";

/** Titular en 2 o menos de los 10 partidos anteriores de su equipo (features/lineup.py) */
export const UNUSUAL_MAX_STARTS = 2;

export function isUnusual(recent: number | null | undefined): boolean {
  return recent != null && recent <= UNUSUAL_MAX_STARTS;
}

/** «Poco habitual: 1 de 10»: solo informa; el modelo ya lo tiene en cuenta */
export function UnusualTag({ recent }: { recent?: number | null }) {
  if (!isUnusual(recent)) return null;
  return <Tag tone="neutral">{`Poco habitual: ${recent} de 10`}</Tag>;
}

export const UNUSUAL_NOTE =
  "Poco habitual: titular en 2 o menos de los 10 partidos anteriores de su equipo. Desde 2023 estos titulares rematan algo menos que en sus titularidades de antes; el modelo ya lo tiene en cuenta.";
