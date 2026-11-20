"use client";

import { ErrorNote, Tag } from "@/components/ui";
import { useApi } from "@/lib/api";
import { num, pct } from "@/lib/format";
import { tr } from "@/lib/i18n";
import type { PickReview, TableVote } from "@/lib/types";

const OUTCOME: Record<string, { tone: string; es: string; en: string }> = {
  aprobado: { tone: "text-tinta", es: "Aprobado por los agentes", en: "Approved by the agents" },
  medianamente: { tone: "text-tarjeta", es: "Medianamente aprobado", en: "Partly approved" },
  desaprobado: { tone: "text-rojo", es: "Desaprobado por los agentes", en: "Rejected by the agents" },
};

function Motive({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <li className="grid gap-x-4 gap-y-0.5 py-2 sm:grid-cols-[14rem_minmax(0,1fr)]">
      <span className="text-nota font-bold">{label}</span>
      <span className="max-w-[72ch] text-interfaz">{children}</span>
    </li>
  );
}

function VoteTag({ vote }: { vote: boolean }) {
  return <Tag tone={vote ? "boli" : "neutral"}>{vote ? tr("Sí", "Yes") : tr("No", "No")}</Tag>;
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

function FirstRound({ votes }: { votes: TableVote[] }) {
  return (
    <div className="min-w-0">
      <h4 className="semi text-base font-bold">{tr("Primera ronda: cada uno solo", "First round: each on their own")}</h4>
      <ul className="mt-1 divide-y divide-regla-suave">
        {votes.map((v) => (
          <li key={v.agent} className="py-2 text-interfaz">
            <span className="mr-2 inline-flex items-center gap-2 font-bold">
              <VoteTag vote={v.vote} />
              {tr(v.name, v.name_en)}
            </span>
            {tr(v.text, v.text_en)}
          </li>
        ))}
      </ul>
    </div>
  );
}

/** La mesa de apostadores debajo de la apuesta del día: siete agentes de Claude votan; una opinión, no un cálculo */
export function Veredicto({ pickId }: { pickId: number }) {
  const { data, error, mutate } = useApi<PickReview | null>(`/picks/${pickId}/review`, {
    refreshInterval: (d) =>
      d?.status === "pendiente" || d?.status === "trabajando" || d?.updating
        ? 15000
        : // Votado sin once confirmado: al confirmarse llega otra votación
          d?.status === "espera" || (d?.status === "lista" && d.stage !== "confirmed")
          ? 60000
          : 0,
  });
  if (error) return <ErrorNote error={error} onRetry={() => mutate()} />;
  if (!data) return null;

  const outcome = data.outcome ? OUTCOME[data.outcome] : undefined;
  if (data.status !== "lista" || !outcome) {
    const text =
      data.status === "espera"
        ? tr("La mesa de apostadores votará cuando salga la alineación.", "The betting table will vote once the lineup is out.")
        : data.status === "error"
          ? // El detalle (a veces el error de los siete agentes) va al registro del worker, no al panel
            tr("La mesa no pudo votar esta vez.", "The table couldn't vote this time.")
          : tr("La mesa de apostadores está votando…", "The betting table is voting…");
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
    data.stage !== "confirmed" && tr("Votado sin alineación confirmada.", "Voted without a confirmed lineup."),
    data.numbers_changed && tr("Los números cambiaron desde esta votación.", "The numbers changed since this vote."),
    data.updating && tr("Hay una votación nueva en marcha.", "A new vote is under way."),
  ].filter(Boolean) as string[];

  return (
    <section aria-label={tr("La mesa de apostadores", "The betting table")} className="mt-6 border-t-[3px] border-tinta pt-3">
      <p className="flex flex-wrap items-baseline gap-x-4 gap-y-1">
        <span className="text-nota font-semibold tracking-[0.08em] text-grafito uppercase">
          {tr("La mesa de apostadores", "The betting table")}
        </span>
        <span className={`cond text-cifra-grande leading-none font-black ${outcome.tone}`}>{tr(outcome.es, outcome.en)}</span>
        <span className="text-nota text-grafito">{tr("La decisión es tuya.", "The decision is yours.")}</span>
      </p>
      <p className="mt-1 text-interfaz">
        {tr(
          `${data.yes} de ${data.total} dicen sí · ${pct(data.yes_share)} del voto con pesos`,
          `${data.yes} of ${data.total} say yes · ${pct(data.yes_share)} of the weighted vote`,
        )}
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
        {(data.votes ?? []).map((v) => (
          <li key={v.agent} className="grid gap-x-4 gap-y-1 py-2 sm:grid-cols-[14rem_minmax(0,1fr)]">
            <span className="inline-flex flex-wrap items-center gap-x-2 text-nota font-bold">
              <VoteTag vote={v.vote} />
              {tr(v.name, v.name_en)}
              <span className="num font-normal text-grafito" title={tr("Peso de su voto", "Weight of their vote")}>
                ×{num(v.weight, 2)}
              </span>
            </span>
            <span className="max-w-[72ch] text-interfaz">
              {tr(v.text, v.text_en)}
              {v.changed && <span className="text-grafito"> {tr("(cambió de opinión)", "(changed their mind)")}</span>}
            </span>
          </li>
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
          "Es una opinión escrita por Claude y todavía no está medida. No cambia el cálculo del modelo. Cada voto empieza valiendo ×1 y sube o baja con lo que habría ganado o perdido (entre ×0.5 y ×2).",
          "It is an opinion written by Claude and it has not been measured yet. It does not change the model's numbers. Each vote starts at ×1 and goes up or down with what it would have won or lost (between ×0.5 and ×2).",
        )}
      </p>

      {data.debate && (
        <details className="mt-1">
          <summary className="inline-flex min-h-10 cursor-pointer items-center text-interfaz font-bold underline underline-offset-4">
            {tr("Ver la conversación", "See the conversation")}
          </summary>
          <div className="mt-2 grid gap-x-10 gap-y-5 pb-2 lg:grid-cols-2">
            {data.round1 && data.round1.length > 0 && (
              <div className="lg:col-span-2">
                <FirstRound votes={data.round1} />
              </div>
            )}
            <Side title={tr("Noticias a favor", "News for")} side={data.debate.favor} />
            <Side title={tr("Noticias en contra", "News against")} side={data.debate.contra} />
          </div>
        </details>
      )}
    </section>
  );
}
