"use client";

import Link from "next/link";
import { useState } from "react";
import { Empty, ErrorNote, Loading, Section, Tag } from "@/components/ui";
import type { ApiError } from "@/lib/api";
import { odds, signedPct, splitMatch } from "@/lib/format";
import { betLabel } from "@/lib/markets";
import type { PriceComparison, PriceEdge } from "@/lib/types";

const th = "py-2 pr-4 text-left text-nota font-semibold text-grafito";
const td = "py-2.5 pr-4 align-middle";

/** De cuándo son los dos precios (casi siempre de la misma descarga de las 08:30) */
function when(r: PriceEdge): string {
  return r.odds_at === r.fair_at ? `Precios del ${r.odds_at}` : `Betano del ${r.odds_at}; Pinnacle del ${r.fair_at}`;
}

function GroupTag({ row }: { row: PriceEdge }) {
  return <Tag tone={row.group === "goles" ? "neutral" : "tarjeta"}>{row.group === "goles" ? "Goles" : "Estadísticas"}</Tag>;
}

/** «Frente a Pinnacle»: cuotas de Betano que pagan más que la justa de Pinnacle, sin modelo */
export function Comparador({ data, error, onRetry }: { data?: PriceComparison; error?: ApiError; onRetry: () => void }) {
  const [all, setAll] = useState(false);
  return (
    <Section
      title="Betano frente a Pinnacle"
      intro={`Cuotas de Betano que pagan al menos un ${Math.round((data?.min_edge ?? 0.02) * 100)} % más que la cuota justa de Pinnacle, la casa más afilada que se descarga. No usa el modelo: es comparar precios. ${data?.note ?? ""}`}
    >
      {error ? (
        <ErrorNote error={error} onRetry={onRetry} />
      ) : !data ? (
        <Loading lines={3} label="Comparando cuotas" />
      ) : data.rows.length === 0 ? (
        <Empty>Hoy ninguna cuota de Betano paga más que la justa de Pinnacle en los partidos que faltan.</Empty>
      ) : (
        <Rows rows={data.rows} all={all} onToggle={() => setAll(!all)} />
      )}
    </Section>
  );
}

function Rows({ rows, all, onToggle }: { rows: PriceEdge[]; all: boolean; onToggle: () => void }) {
  const shown = all ? rows : rows.slice(0, 12);
  return (
    <>
      <ul className="divide-y divide-regla-suave border-y border-regla-suave lg:hidden">
        {shown.map((r, i) => {
          const [home, away] = splitMatch(r.match);
          return (
            <li key={i} className="py-3">
              <div className="flex items-start justify-between gap-4">
                <span className="font-semibold">{betLabel(r.market, r.selection, r.line, { home, away })}</span>
                <span className="cond num text-2xl leading-none font-bold">{odds(r.odds)}</span>
              </div>
              <p className="mt-0.5 text-nota text-grafito">
                <Link href={`/partidos/${r.match_id}`} className="underline decoration-regla underline-offset-2">
                  {r.match}
                </Link>
                , {r.kickoff_local}
              </p>
              <p className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-nota">
                <span>
                  Justa de Pinnacle <strong className="num">{odds(r.fair_odds)}</strong>
                </span>
                <span>
                  Ventaja <strong className="num text-boli">{signedPct(r.edge)}</strong>
                </span>
                <GroupTag row={r} />
              </p>
              <p className="mt-1 text-nota text-grafito">{when(r)}.</p>
            </li>
          );
        })}
      </ul>
      <div className="hidden overflow-x-auto lg:block">
        <table className="w-full min-w-[600px] border-collapse text-interfaz">
          <thead className="border-b border-tinta">
            <tr>
              <th className={th}>Partido</th>
              <th className={th}>Apuesta</th>
              <th className={`${th} text-right`}>Betano</th>
              <th className={`${th} text-right`}>Justa de Pinnacle</th>
              <th className={`${th} text-right`}>Ventaja</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => {
              const [home, away] = splitMatch(r.match);
              return (
                <tr key={i} className="border-b border-regla-suave">
                  <td className={`${td} max-w-56`}>
                    <Link href={`/partidos/${r.match_id}`} className="hover:text-boli hover:underline">
                      {r.match}
                    </Link>
                    <span className="block text-nota text-grafito">{r.kickoff_local}</span>
                  </td>
                  <td className={td}>
                    {betLabel(r.market, r.selection, r.line, { home, away })}
                    <span className="mt-1 flex flex-wrap items-center gap-x-2 text-nota text-grafito">
                      <GroupTag row={r} />
                      {when(r)}
                    </span>
                  </td>
                  <td className={`${td} num cond text-right text-xl font-extrabold`}>{odds(r.odds)}</td>
                  <td className={`${td} num text-right text-grafito`}>{odds(r.fair_odds)}</td>
                  <td className={`${td} num text-right font-semibold text-boli`}>{signedPct(r.edge)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {rows.length > 12 && (
        <button type="button" onClick={onToggle} className="mt-1 inline-flex min-h-10 items-center text-interfaz font-semibold text-boli underline underline-offset-4">
          {all ? "Mostrar menos" : `Mostrar las ${rows.length}`}
        </button>
      )}
    </>
  );
}
