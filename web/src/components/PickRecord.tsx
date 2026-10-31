"use client";

import Link from "next/link";
import { Figure } from "@/components/ui";
import { useApi } from "@/lib/api";
import { int, pct, shortDate, signedPct } from "@/lib/format";
import { tr } from "@/lib/i18n";
import type { QualifiedPicks, PickRecord as Record } from "@/lib/types";

function units(u: number): string {
  return `${u > 0 ? "+" : ""}${u.toFixed(2)} u`;
}

function toneClass(v: number | null | undefined): string {
  return v == null || v === 0 ? "" : v > 0 ? "text-boli" : "text-rojo";
}

const sources = () => ({
  // La apuesta del día: una por día como mucho
  dia: {
    path: "/picks/record",
    title: tr("Aciertos de la apuesta del día", "Bet of the day record"),
    who: tr("Todas las que eligió el sistema", "Every one the system picked"),
  },
  // Todas las que pasaron el corte de valor, probabilidad y confianza (la apuesta del día es una de ellas)
  corte: {
    path: "/picks/qualified",
    title: tr("Aciertos de las que pasan el corte", "Record of bets that pass the cut"),
    who: tr("Todas las que pasaron el corte de valor, probabilidad y confianza", "Every bet that passed the value, probability and confidence cut"),
  },
});

/** Contador de aciertos desde el primer día del sistema: de la apuesta del día o de todas las que pasan el corte. */
export function PickRecord({
  variant = "card",
  source = "dia",
}: {
  variant?: "card" | "row" | "line";
  source?: "dia" | "corte";
}) {
  const src = sources()[source];
  const { data } = useApi<Record | QualifiedPicks>(src.path);
  if (!data) return null;
  const r = "record" in data ? data.record : data;
  const decided = r.hits + r.misses;
  const tone = r.profit_units > 0 ? "boli" : r.profit_units < 0 ? "rojo" : undefined;
  const sinceDate = r.since ? shortDate(r.since) : null;
  const since = sinceDate ? tr(`desde el ${sinceDate}`, `since ${sinceDate}`) : tr("desde el inicio", "since the start");
  const of = (a: number, b: number) => tr(`${int(a)} de ${int(b)}`, `${int(a)} of ${int(b)}`);

  if (variant === "line") {
    const pending = tr(`${int(r.pending)} por jugarse`, `${int(r.pending)} still to play`);
    return (
      <p className="mb-4 border-t-[3px] border-boli bg-hoja px-3 py-2 text-interfaz">
        {r.settled === 0 ? (
          <>
            {tr(
              `Las que pasan el corte se guardan y se liquidan solas: aún no terminó ninguna (${pending}). `,
              `Bets that pass the cut are saved and settled on their own: none has finished yet (${pending}). `,
            )}
          </>
        ) : (
          <>
            {tr(`Las que pasan el corte, ${since}: `, `Bets that pass the cut, ${since}: `)}
            <strong className="num">{of(r.hits, decided)}</strong> {tr("aciertos", "won")} ({pct(r.hit_rate)}){" "}
            {tr("y", "and")}{" "}
            <strong className={`num ${tone === "boli" ? "text-boli" : tone === "rojo" ? "text-rojo" : ""}`}>
              {units(r.profit_units)}
            </strong>{" "}
            {tr("con 1 u por apuesta", "staking 1 u per bet")}; {pending}.{" "}
            {r.avg_clv != null && (
              <>
                {tr("CLV medio", "Average CLV")}{" "}
                <strong className={`num ${toneClass(r.avg_clv)}`}>{signedPct(r.avg_clv)}</strong>{" "}
                {tr(
                  `frente a Pinnacle sin margen antes del partido (${int(r.with_clv)} con referencia).`,
                  `against margin-free Pinnacle before kick-off (${int(r.with_clv)} with a reference).`,
                )}{" "}
              </>
            )}
          </>
        )}
        <Link href="/rendimiento#corte" className="font-semibold text-boli underline underline-offset-4">
          {tr("Ver historial", "See history")}
        </Link>
      </p>
    );
  }

  if (variant === "row") {
    return (
      <div className="mb-8">
        <h3 className="semi mb-3 text-base font-bold">
          {tr("Desde el inicio", "Since the start")} ({sinceDate ?? tr("el inicio", "the start")})
        </h3>
        <div className={`grid grid-cols-2 gap-x-8 gap-y-6 ${source === "corte" ? "sm:grid-cols-4 lg:grid-cols-7" : "sm:grid-cols-6"}`}>
          <Figure value={of(r.hits, decided)} label={tr("aciertos", "won")} tone={r.hits > 0 ? "boli" : undefined} />
          <Figure value={pct(r.hit_rate)} label={tr("acierto (sin devueltas)", "hit rate (no refunds)")} />
          <Figure value={int(r.misses)} label={tr("falladas", "lost")} />
          <Figure value={int(r.pushes)} label={tr("devueltas", "refunded")} />
          <Figure value={int(r.pending)} label={tr("por jugarse", "still to play")} />
          <Figure value={units(r.profit_units)} label={tr(`beneficio (ROI ${signedPct(r.roi)})`, `profit (ROI ${signedPct(r.roi)})`)} tone={tone} />
          {source === "corte" && (
            <Figure
              value={signedPct(r.avg_clv)}
              label={tr(`CLV medio (${int(r.with_clv)} con referencia)`, `average CLV (${int(r.with_clv)} with a reference)`)}
              tone={r.avg_clv == null || r.avg_clv === 0 ? undefined : r.avg_clv > 0 ? "boli" : "rojo"}
            />
          )}
        </div>
      </div>
    );
  }

  return (
    <section aria-labelledby={`record-${source}`} className="border-t-[3px] border-tinta pt-3">
      <h2 id={`record-${source}`} className="cond text-lateral leading-none font-black uppercase">
        {src.title}
      </h2>
      <p className="mt-1 mb-4 text-nota text-grafito">
        {src.who}, {since}.
      </p>
      {r.settled === 0 ? (
        <p className="text-nota text-grafito">
          {tr("Aún no terminó ninguna.", "None has finished yet.")}{" "}
          {r.pending === 1
            ? tr("Hay 1 por jugarse.", "1 still to play.")
            : tr(`Hay ${int(r.pending)} por jugarse.`, `${int(r.pending)} still to play.`)}
        </p>
      ) : (
        <>
          <div className="flex items-end gap-6">
            <Figure size="lg" value={of(r.hits, decided)} label={tr("aciertos", "won")} tone={r.hits > 0 ? "boli" : undefined} />
            <Figure value={pct(r.hit_rate)} label={tr("de acierto", "hit rate")} />
          </div>
          <dl className="mt-4 grid grid-cols-2 gap-x-4 gap-y-1 text-nota">
            <dt className="text-grafito">{tr("Falladas", "Lost")}</dt>
            <dd className="num text-right">{int(r.misses)}</dd>
            {r.pushes > 0 && (
              <>
                <dt className="text-grafito">{tr("Devueltas", "Refunded")}</dt>
                <dd className="num text-right">{int(r.pushes)}</dd>
              </>
            )}
            <dt className="text-grafito">{tr("Por jugarse", "Still to play")}</dt>
            <dd className="num text-right">{int(r.pending)}</dd>
            <dt className="text-grafito">{tr("Beneficio (1 u por apuesta)", "Profit (1 u per bet)")}</dt>
            <dd className={`num text-right font-semibold ${tone === "boli" ? "text-boli" : tone === "rojo" ? "text-rojo" : ""}`}>
              {units(r.profit_units)}
            </dd>
          </dl>
        </>
      )}
    </section>
  );
}
