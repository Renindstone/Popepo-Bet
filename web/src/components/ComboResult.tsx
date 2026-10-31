"use client";

import { Tag } from "@/components/ui";
import { odds, pct, signedPct } from "@/lib/format";
import { tr } from "@/lib/i18n";
import type { CaptureCombo } from "@/lib/types";

const COMBO_TONE: Record<string, "boli" | "rojo" | "tarjeta" | "neutral"> = {
  "con valor": "boli",
  "sin valor": "rojo",
  "no evaluable": "tarjeta",
};

/** Veredicto de la API (en español, es la clave del tono) en el idioma en uso */
export function comboVerdictText(verdict: string): string {
  const en: Record<string, string> = {
    "con valor": "value",
    "sin valor": "no value",
    "no evaluable": "can't evaluate",
    "sin cuota para comparar": "no odds to compare",
  };
  return tr(verdict, en[verdict] ?? verdict);
}

/** Resultado de una combinada o Bet Builder: probabilidad de cada partido y del total según el modelo. */
export function ComboResult({ combo }: { combo: CaptureCombo }) {
  return (
    <div className="space-y-3">
      <p className="max-w-[75ch] text-nota text-grafito">
        {tr(
          "Dentro de un mismo partido las selecciones dependen entre sí, así que su probabilidad conjunta sale de la matriz de marcadores del modelo, incluidos los goles y asistencias de jugadores (cada gol del equipo se reparte entre sus jugadores). Los partidos distintos se multiplican. Córners, tarjetas, remates y faltas se combinan como si no dependieran del resultado: el total sale aproximado.",
          "Within one match the selections depend on each other, so their joint probability comes from the model's scoreline matrix, player goals and assists included (each team goal is shared among its players). Different matches are multiplied. Corners, cards, shots and fouls are combined as if they did not depend on the result: the total is approximate.",
        )}
      </p>
      <ul className="space-y-2">
        {combo.blocks.map((b, i) => (
          <li key={i} className="border border-regla-suave px-3 py-2.5">
            <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
              <p className="font-semibold">
                {b.match}
                {b.kickoff_local && <span className="ml-2 text-nota font-normal text-grafito">{b.kickoff_local.slice(5)}</span>}
              </p>
              <p className="num text-nota">
                {b.odds != null && <span className="font-semibold">{odds(b.odds)}</span>}
                {b.prob != null && (
                  <span className="ml-3 text-grafito">
                    {tr("modelo", "model")} {pct(b.prob)} · {tr("justa", "fair")} {odds(b.fair_odds)}
                    {b.ev != null && (
                      <span className={`ml-2 font-semibold ${b.ev > 0 ? "text-boli" : "text-rojo"}`}>{signedPct(b.ev)}</span>
                    )}
                  </span>
                )}
              </p>
            </div>
            <ul className="mt-1 text-nota">
              {b.legs.map((lg, k) => (
                <li key={k} className={lg.market === "otro" ? "text-rojo" : ""}>
                  · {lg.label}
                </li>
              ))}
            </ul>
            {b.reason && (
              <p className="mt-1 text-nota text-rojo">
                {tr("No evaluable:", "Can't evaluate:")} {b.reason}
              </p>
            )}
            {b.notes.length > 0 && <p className="mt-1 text-nota text-grafito">{b.notes.join(" · ")}</p>}
          </li>
        ))}
      </ul>
      <div className="flex flex-wrap items-center gap-x-6 gap-y-2 border-t border-regla pt-3">
        <span className="font-semibold">Total</span>
        <span className="num">
          {tr("cuota", "odds")} {odds(combo.total_odds)}
        </span>
        {combo.prob != null && (
          <span className="num text-grafito">
            {tr("modelo", "model")} {pct(combo.prob, 1)} · {tr("justa", "fair")} {odds(combo.fair_odds)}
          </span>
        )}
        {combo.ev != null && (
          <span className={`num font-semibold ${combo.ev > 0 ? "text-boli" : "text-rojo"}`}>{signedPct(combo.ev)}</span>
        )}
        <Tag tone={COMBO_TONE[combo.verdict] ?? "neutral"}>{comboVerdictText(combo.verdict)}</Tag>
        {combo.approximate && combo.evaluable && <Tag tone="tarjeta">{tr("aproximado", "approximate")}</Tag>}
      </div>
    </div>
  );
}
