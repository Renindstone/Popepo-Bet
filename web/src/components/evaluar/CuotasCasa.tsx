"use client";

import { useState } from "react";
import { Empty, ErrorNote, Loading, Tag } from "@/components/ui";
import { useApi } from "@/lib/api";
import { odds, pct, signedPct } from "@/lib/format";
import { marketName } from "@/lib/markets";
import { addLeg, updateSlip, useSlip } from "@/lib/slip";
import type { BookOdd, BookOdds, MatchSummary } from "@/lib/types";

const VERDICT: Record<string, { text: string; tone: "boli" | "tarjeta" | "neutral" }> = {
  APOSTAR: { text: "Apostar", tone: "boli" },
  "valor pequeño o poca confianza": { text: "Valor pequeño", tone: "tarjeta" },
  "NO apostar": { text: "No", tone: "neutral" },
};
const STAT_MARKETS = /corners|cards|shots|sot|fouls/;

/**
 * Cuotas de Betano que ya se descargaron para este partido (OddsPapi), evaluadas por el modelo: sin captura ni IA.
 * Cada una se puede evaluar en el formulario o añadir al cupón.
 */
export function CuotasCasa({ match, onUse }: { match: MatchSummary; onUse: (o: BookOdd) => void }) {
  const { data, error, mutate } = useApi<BookOdds>(`/matches/${match.match_id}/odds?bookmaker=betano`);
  const [all, setAll] = useState(false);
  const slip = useSlip();
  const teams = { home: match.home, away: match.away };

  if (error) return <ErrorNote error={error} onRetry={() => mutate()} />;
  if (!data) return <Loading lines={4} label="Cargando cuotas de Betano" />;
  if (data.odds.length === 0) {
    return <Empty>No hay cuotas de Betano guardadas para este partido (se descargan cada mañana a las 08:30).</Empty>;
  }

  const rows = all ? data.odds : data.odds.filter((o) => o.ev > 0);
  const groups = new Map<string, BookOdd[]>();
  for (const o of rows) groups.set(o.market, [...(groups.get(o.market) ?? []), o]);
  const order = ["1x2", "dc", "btts", "ou_goals", "eh", "ah"];
  const sorted = [...groups.entries()].sort(
    ([a], [b]) => (order.indexOf(a) + 1 || 99) - (order.indexOf(b) + 1 || 99) || a.localeCompare(b),
  );

  function toSlip(o: BookOdd) {
    if (slip.legs.length === 0) updateSlip((s) => ({ ...s, bookmaker: "betano" }));
    addLeg({
      matchId: String(match.match_id),
      match: `${match.home} vs ${match.away}`,
      home: match.home,
      away: match.away,
      kickoff: match.kickoff_local,
      market: o.market,
      selection: o.selection,
      line: o.line,
      player: null,
      odds: o.odds,
      label: o.label,
    });
  }

  return (
    <div>
      <div className="mb-3 flex flex-wrap items-center justify-between gap-3">
        <p className="text-nota text-grafito">
          Guardadas el {data.captured_local?.slice(8, 10)}/{data.captured_local?.slice(5, 7)} a las{" "}
          {data.captured_local?.slice(11)}: la cuota en Betano puede haber cambiado. {data.odds.length} cuotas,{" "}
          {data.odds.filter((o) => o.ev > 0).length} con valor positivo.
        </p>
        <div className="flex gap-1">
          {[
            [false, "Con valor"],
            [true, "Todas"],
          ].map(([value, label]) => (
            <button
              key={String(value)}
              type="button"
              aria-pressed={all === value}
              onClick={() => setAll(value as boolean)}
              className={`h-9 rounded-[3px] border px-3 text-interfaz font-semibold ${
                all === value ? "border-tinta bg-tinta text-papel" : "border-regla bg-hoja text-grafito hover:text-tinta"
              }`}
            >
              {label as string}
            </button>
          ))}
        </div>
      </div>
      {rows.length === 0 ? (
        <Empty>Ninguna cuota de Betano de este partido tiene valor según el modelo.</Empty>
      ) : (
        <div className="space-y-2">
          {sorted.map(([market, items]) => (
            <details key={market} open={!all || ["1x2", "dc", "btts"].includes(market)} className="rounded-[3px] border border-regla-suave">
              <summary className="cursor-pointer px-3 py-2 font-semibold">
                {marketName(market, teams)} <span className="font-normal text-grafito">({items.length})</span>
                {STAT_MARKETS.test(market) && (
                  <span className="ml-2 text-nota font-normal text-grafito">sin validar con cuotas reales: con cautela</span>
                )}
              </summary>
              <table className="w-full text-nota">
                <tbody>
                  {[...items]
                    .sort((a, b) => (a.line ?? 0) - (b.line ?? 0) || a.selection.localeCompare(b.selection))
                    .map((o) => {
                      const v = VERDICT[o.verdict] ?? { text: o.verdict, tone: "neutral" as const };
                      return (
                        <tr key={`${o.selection}-${o.line}`} className="border-t border-regla-suave">
                          {/* En el celular el veredicto va debajo del nombre y las acciones, una sobre otra */}
                          <td className="py-1.5 pr-3 pl-3">
                            {o.label}
                            <span className="mt-1 block sm:hidden">
                              <Tag tone={v.tone}>{v.text}</Tag>
                            </span>
                          </td>
                          <td className="num py-1.5 pr-3 text-right font-semibold">{odds(o.odds)}</td>
                          <td className="num hidden py-1.5 pr-3 text-right text-grafito sm:table-cell">{pct(o.prob)}</td>
                          <td className={`num py-1.5 pr-3 text-right font-semibold ${o.ev > 0 ? "text-boli" : "text-rojo"}`}>
                            {signedPct(o.ev)}
                          </td>
                          <td className="hidden py-1.5 pr-3 sm:table-cell">
                            <Tag tone={v.tone}>{v.text}</Tag>
                          </td>
                          <td className="py-1 pr-3">
                            <div className="flex flex-col items-end whitespace-nowrap sm:flex-row sm:justify-end sm:gap-3">
                              <button
                                type="button"
                                onClick={() => onUse(o)}
                                className="min-h-7 font-semibold text-boli underline underline-offset-4"
                              >
                                Evaluar
                              </button>
                              <button
                                type="button"
                                onClick={() => toSlip(o)}
                                aria-label={`Añadir ${o.label} al cupón`}
                                className="min-h-7 font-semibold text-grafito underline underline-offset-4 hover:text-tinta"
                              >
                                + Cupón
                              </button>
                            </div>
                          </td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </details>
          ))}
        </div>
      )}
    </div>
  );
}
