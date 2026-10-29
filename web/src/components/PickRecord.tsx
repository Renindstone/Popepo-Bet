"use client";

import Link from "next/link";
import { Figure } from "@/components/ui";
import { useApi } from "@/lib/api";
import { int, pct, shortDate, signedPct } from "@/lib/format";
import type { QualifiedPicks, PickRecord as Record } from "@/lib/types";

function units(u: number): string {
  return `${u > 0 ? "+" : ""}${u.toFixed(2)} u`;
}

function toneClass(v: number | null | undefined): string {
  return v == null || v === 0 ? "" : v > 0 ? "text-boli" : "text-rojo";
}

const SOURCES = {
  // La apuesta del día: una por día como mucho
  dia: { path: "/picks/record", title: "Aciertos de la apuesta del día", who: "Todas las que eligió el sistema" },
  // Todas las que pasaron el corte de valor, probabilidad y confianza (la apuesta del día es una de ellas)
  corte: {
    path: "/picks/qualified",
    title: "Aciertos de las que pasan el corte",
    who: "Todas las que pasaron el corte de valor, probabilidad y confianza",
  },
} as const;

/** Contador de aciertos desde el primer día del sistema: de la apuesta del día o de todas las que pasan el corte. */
export function PickRecord({
  variant = "card",
  source = "dia",
}: {
  variant?: "card" | "row" | "line";
  source?: keyof typeof SOURCES;
}) {
  const src = SOURCES[source];
  const { data } = useApi<Record | QualifiedPicks>(src.path);
  if (!data) return null;
  const r = "record" in data ? data.record : data;
  const decided = r.hits + r.misses;
  const tone = r.profit_units > 0 ? "boli" : r.profit_units < 0 ? "rojo" : undefined;
  const since = r.since ? `desde el ${shortDate(r.since)}` : "desde el inicio";

  if (variant === "line") {
    const pending = r.pending === 1 ? "1 por jugarse" : `${int(r.pending)} por jugarse`;
    return (
      <p className="mb-4 border-l-[3px] border-boli bg-hoja px-3 py-2 text-interfaz">
        {r.settled === 0 ? (
          <>Las que pasan el corte se guardan y se liquidan solas: aún no terminó ninguna ({pending}). </>
        ) : (
          <>
            Las que pasan el corte, {since}: <strong className="num">{`${int(r.hits)} de ${int(decided)}`}</strong>{" "}
            aciertos ({pct(r.hit_rate)}) y{" "}
            <strong className={`num ${tone === "boli" ? "text-boli" : tone === "rojo" ? "text-rojo" : ""}`}>
              {units(r.profit_units)}
            </strong>{" "}
            con 1 u por apuesta; {pending}.{" "}
            {r.avg_clv != null && (
              <>
                CLV medio <strong className={`num ${toneClass(r.avg_clv)}`}>{signedPct(r.avg_clv)}</strong> frente a
                Pinnacle sin margen antes del partido ({int(r.with_clv)} con referencia).{" "}
              </>
            )}
          </>
        )}
        <Link href="/rendimiento#corte" className="font-semibold text-boli underline underline-offset-4">
          Ver historial
        </Link>
      </p>
    );
  }

  if (variant === "row") {
    return (
      <div className="mb-8">
        <h3 className="semi mb-3 text-base font-bold">Desde el inicio ({since.replace("desde el ", "")})</h3>
        <div className={`grid grid-cols-2 gap-x-8 gap-y-6 ${source === "corte" ? "sm:grid-cols-4 lg:grid-cols-7" : "sm:grid-cols-6"}`}>
          <Figure value={`${int(r.hits)} de ${int(decided)}`} label="aciertos" tone={r.hits > 0 ? "boli" : undefined} />
          <Figure value={pct(r.hit_rate)} label="acierto (sin devueltas)" />
          <Figure value={int(r.misses)} label="falladas" />
          <Figure value={int(r.pushes)} label="devueltas" />
          <Figure value={int(r.pending)} label="por jugarse" />
          <Figure value={units(r.profit_units)} label={`beneficio (ROI ${signedPct(r.roi)})`} tone={tone} />
          {source === "corte" && (
            <Figure
              value={signedPct(r.avg_clv)}
              label={`CLV medio (${int(r.with_clv)} con referencia)`}
              tone={r.avg_clv == null || r.avg_clv === 0 ? undefined : r.avg_clv > 0 ? "boli" : "rojo"}
            />
          )}
        </div>
      </div>
    );
  }

  return (
    <section aria-labelledby={`record-${source}`} className="rounded-[4px] border border-regla bg-hoja p-5">
      <h2 id={`record-${source}`} className="semi text-base font-bold text-tinta">
        {src.title}
      </h2>
      <p className="mb-4 text-nota text-grafito">
        {src.who}, {since}.
      </p>
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
