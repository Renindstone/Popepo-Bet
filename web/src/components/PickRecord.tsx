"use client";

import { Figure } from "@/components/ui";
import { useApi } from "@/lib/api";
import { int, pct, shortDate, signedPct } from "@/lib/format";
import type { PickRecord as Record } from "@/lib/types";

function units(u: number): string {
  return `${u > 0 ? "+" : ""}${u.toFixed(2)} u`;
}

/** Contador de aciertos de la apuesta del día desde el primer día del sistema. */
export function PickRecord({ variant = "card" }: { variant?: "card" | "row" }) {
  const { data: r } = useApi<Record>("/picks/record");
  if (!r) return null;
  const decided = r.hits + r.misses;
  const tone = r.profit_units > 0 ? "boli" : r.profit_units < 0 ? "rojo" : undefined;
  const since = r.since ? `desde el ${shortDate(r.since)}` : "desde el inicio";

  if (variant === "row") {
    return (
      <div className="mb-8">
        <h3 className="semi mb-3 text-base font-bold">Desde el inicio ({since.replace("desde el ", "")})</h3>
        <div className="grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-6">
          <Figure value={`${int(r.hits)} de ${int(decided)}`} label="aciertos" tone={r.hits > 0 ? "boli" : undefined} />
          <Figure value={pct(r.hit_rate)} label="acierto (sin devueltas)" />
          <Figure value={int(r.misses)} label="falladas" />
          <Figure value={int(r.pushes)} label="devueltas" />
          <Figure value={int(r.pending)} label="por jugarse" />
          <Figure value={units(r.profit_units)} label={`beneficio (ROI ${signedPct(r.roi)})`} tone={tone} />
        </div>
      </div>
    );
  }

  return (
    <section aria-labelledby="record-titulo" className="rounded-[4px] border border-regla bg-hoja p-5">
      <h2 id="record-titulo" className="semi text-base font-bold text-tinta">
        Aciertos de la apuesta del día
      </h2>
      <p className="mb-4 text-nota text-grafito">Todas las que eligió el sistema, {since}.</p>
      {r.settled === 0 ? (
        <p className="text-nota text-grafito">
          Aún no terminó ninguna. {r.pending === 1 ? "Hay 1 por jugarse." : `Hay ${int(r.pending)} por jugarse.`}
        </p>
      ) : (
        <>
          <div className="flex items-end gap-6">
            <Figure size="lg" value={`${int(r.hits)} de ${int(decided)}`} label="aciertos" tone={r.hits > 0 ? "boli" : undefined} />
            <Figure value={pct(r.hit_rate)} label="de acierto" />
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1 text-nota">
            <dt className="text-grafito">Falladas</dt>
            <dd className="num text-right">{int(r.misses)}</dd>
            {r.pushes > 0 && (
              <>
                <dt className="text-grafito">Devueltas</dt>
                <dd className="num text-right">{int(r.pushes)}</dd>
              </>
            )}
            <dt className="text-grafito">Por jugarse</dt>
            <dd className="num text-right">{int(r.pending)}</dd>
            <dt className="text-grafito">Beneficio (1 u por apuesta)</dt>
            <dd className={`num text-right font-semibold ${tone === "boli" ? "text-boli" : tone === "rojo" ? "text-rojo" : ""}`}>
              {units(r.profit_units)}
            </dd>
          </dl>
        </>
      )}
    </section>
  );
}
