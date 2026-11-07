"use client";

import { ErrorNote } from "@/components/ui";
import { useApi } from "@/lib/api";
import { pct } from "@/lib/format";
import { tr } from "@/lib/i18n";
import type { PickReview } from "@/lib/types";

const WORD_TONE: Record<string, string> = { "Mejor no": "text-rojo", Dudosa: "text-tarjeta", Apostar: "text-tinta" };

function wordText(word: string): string {
  return tr(word, { Apostar: "Bet", Dudosa: "Doubtful", "Mejor no": "Better not" }[word] ?? word);
}

function Motive({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <li className="grid gap-x-4 gap-y-0.5 py-2 sm:grid-cols-[7rem_minmax(0,1fr)]">
      <span className="text-nota font-bold">{label}</span>
      <span className="max-w-[72ch] text-interfaz">{children}</span>
    </li>
  );
}

function Side({ title, side }: { title: string; side: { text: string | null; sources: { title: string; url: string }[] } }) {
  return (
    <div className="min-w-0">
      <h4 className="semi text-base font-bold">{title}</h4>
      <p className="mt-1 text-interfaz leading-relaxed whitespace-pre-line">{side.text}</p>
      {side.sources.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-nota">
          {side.sources.map((s) => (
            <li key={s.url}>
              <a href={s.url} target="_blank" rel="noopener noreferrer nofollow" className="underline underline-offset-2">
                {s.title}
              </a>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}

/** Veredicto de los revisores (A favor, En contra y Juez) debajo de la apuesta del día: una opinión, no un cálculo */
export function Veredicto({ pickId }: { pickId: number }) {
  const { data, error, mutate } = useApi<PickReview | null>(`/picks/${pickId}/review`, {
    refreshInterval: (d) =>
      d?.status === "pendiente" || d?.status === "trabajando" || d?.updating
        ? 15000
        : // Revisado sin once confirmado: al confirmarse llega otra revisión
          d?.status === "espera" || (d?.status === "lista" && d.stage !== "confirmed")
          ? 60000
          : 0,
  });
  if (error) return <ErrorNote error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  if (data.status !== "lista" || !data.word) {
    const text =
      data.status === "espera"
        ? tr("Los revisores la leerán cuando salga la alineación.", "The reviewers will read it once the lineup is out.")
        : data.status === "error"
          ? tr(`Los revisores no pudieron terminar: ${data.error ?? ""}`, `The reviewers could not finish: ${data.error ?? ""}`)
          : tr("Los revisores están leyendo…", "The reviewers are reading…");
    return (
      <p role="status" className="mt-5 text-nota text-grafito">
        {text}
      </p>
    );
  }

  const c = data.confidence ?? 0;
  const t = data.threshold ?? 0.8;
  const r = data.record;
  const notices = [
    data.stage !== "confirmed" && tr("Revisado sin alineación confirmada.", "Reviewed without a confirmed lineup."),
    data.numbers_changed && tr("Los números cambiaron desde esta revisión.", "The numbers changed since this review."),
    data.updating && tr("Hay una revisión nueva en marcha.", "A new review is under way."),
  ].filter(Boolean) as string[];

  return (
    <section aria-label={tr("Veredicto de los revisores", "Reviewers' verdict")} className="mt-6 border-t-[3px] border-tinta pt-3">
      <p className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="text-nota font-semibold tracking-[0.08em] text-grafito uppercase">
          {tr("Veredicto de los revisores", "Reviewers' verdict")}
        </span>
        <span className={`cond text-cifra-grande leading-none font-black ${WORD_TONE[data.word] ?? ""}`}>{wordText(data.word)}</span>
        <span className="text-nota text-grafito">{tr("La decisión es tuya.", "The decision is yours.")}</span>
      </p>

      <ul className="mt-2 divide-y divide-regla-suave border-y border-regla-suave">
        <Motive label={tr("Confianza", "Confidence")}>
          {c >= t
            ? tr(`${pct(c)}, llega a tu ${pct(t)}.`, `${pct(c)}, meets your ${pct(t)}.`)
            : tr(`${pct(c)}, por debajo de tu ${pct(t)}.`, `${pct(c)}, below your ${pct(t)}.`)}{" "}
          {r &&
            tr(
              `Las que pasaron el corte con ${pct(t)} o más: ${r.high.hits} ganadas y ${r.high.misses} perdidas; con menos: ${r.low.hits} y ${r.low.misses}.`,
              `Bets that passed the cut with ${pct(t)} or more: ${r.high.hits} won and ${r.high.misses} lost; with less: ${r.low.hits} and ${r.low.misses}.`,
            )}
        </Motive>
        {(data.streaks ?? []).map((st) => (
          <Motive key={st.team} label={tr("Racha", "Form")}>
            {st.run >= 3
              ? tr(`Va contra ${st.team}, que lleva ${st.run} victorias seguidas.`, `It goes against ${st.team}, on ${st.run} straight wins.`)
              : tr(
                  `Va contra ${st.team}, que ganó ${st.wins} de sus últimos ${st.played} partidos.`,
                  `It goes against ${st.team}, who won ${st.wins} of their last ${st.played} matches.`,
                )}
          </Motive>
        ))}
        {(data.motives ?? []).map((m) => (
          <Motive key={m.label + m.text} label={m.label}>
            {m.text}
          </Motive>
        ))}
      </ul>

      {notices.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-nota text-tarjeta">
          {notices.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
      <p className="mt-2 text-nota text-grafito">
        {tr(
          "Es una opinión escrita por Claude y todavía no está medida. No cambia el cálculo del modelo.",
          "It is an opinion written by Claude and it has not been measured yet. It does not change the model's numbers.",
        )}
      </p>

      {data.debate && (
        <details className="mt-1">
          <summary className="inline-flex min-h-10 cursor-pointer items-center text-interfaz font-bold underline underline-offset-4">
            {tr("Ver la discusión completa", "See the full discussion")}
          </summary>
          <div className="mt-2 grid gap-x-10 gap-y-5 pb-2 lg:grid-cols-2">
            <Side title={tr("A favor", "For")} side={data.debate.favor} />
            <Side title={tr("En contra", "Against")} side={data.debate.contra} />
          </div>
        </details>
      )}
    </section>
  );
}
