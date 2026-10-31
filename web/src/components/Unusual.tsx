import { Tag } from "@/components/ui";
import { tr } from "@/lib/i18n";

/** Titular en 2 o menos de los 10 partidos anteriores de su equipo (features/lineup.py) */
export const UNUSUAL_MAX_STARTS = 2;

export function isUnusual(recent: number | null | undefined): boolean {
  return recent != null && recent <= UNUSUAL_MAX_STARTS;
}

/** «Poco habitual: 1 de 10»: solo informa; el modelo ya lo tiene en cuenta */
export function UnusualTag({ recent }: { recent?: number | null }) {
  if (!isUnusual(recent)) return null;
  return <Tag tone="neutral">{tr(`Poco habitual: ${recent} de 10`, `Unusual: ${recent} of 10`)}</Tag>;
}

export function unusualNote(): string {
  return tr(
    "Poco habitual: titular en 2 o menos de los 10 partidos anteriores de su equipo. Desde 2023 estos titulares rematan algo menos que en sus titularidades de antes; el modelo ya lo tiene en cuenta.",
    "Unusual: started 2 or fewer of their team's previous 10 matches. Since 2023 these starters shoot a bit less than in their earlier starts; the model already accounts for it.",
  );
}
