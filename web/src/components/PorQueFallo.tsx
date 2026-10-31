"use client";

import { NotaClaude } from "@/components/NotaClaude";
import { itemText } from "@/components/semana/Ranking";
import { reasonText } from "@/components/semana/Radar";
import { ErrorNote, Loading } from "@/components/ui";
import { useApi } from "@/lib/api";
import { signedNum } from "@/lib/format";
import { tr } from "@/lib/i18n";
import type { FailureReport, WeekItem } from "@/lib/types";

function tone(n: number): string {
  return n > 0 ? "text-boli" : n < 0 ? "text-rojo" : "text-grafito";
}

function Items({ title, score, items }: { title: string; score: number; items: WeekItem[] }) {
  return (
    <div>
      <p className="text-interfaz font-bold">
        {title} <span className={`num ml-1 ${tone(score)}`}>{signedNum(score)}</span>
      </p>
      <ul className="mt-0.5 space-y-0.5 text-nota">
        {items.map((i) => (
          <li key={i.item} className="flex justify-between gap-4">
            <span className="text-grafito">{itemText(i)}</span>
            <span className={`num shrink-0 font-semibold ${tone(i.score)}`}>{signedNum(i.score)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Lo que se salió de lo esperado en una apuesta del día perdida y si «Sorpresas» ya lo avisaba */
export function PorQueFallo({ pickId }: { pickId: number }) {
  const { data, error, mutate } = useApi<FailureReport>(`/picks/${pickId}/failure`, {
    refreshInterval: (d) => (d?.note?.status === "pendiente" || d?.note?.status === "trabajando" ? 15000 : 0),
  });
  return (
    <section aria-label={tr("Por qué falló", "Why it lost")} className="mt-6 border-t-[3px] border-tinta pt-3">
      <h3 className="cond text-lateral leading-none font-black uppercase">{tr("Por qué falló", "Why it lost")}</h3>
      {error ? (
        <ErrorNote error={error} onRetry={() => mutate()} />
      ) : !data ? (
        <Loading lines={3} label={tr("Comparando la previa con lo que pasó", "Comparing the preview with what happened")} />
      ) : (
        <>
          <p className="mt-1 mb-4 max-w-[72ch] text-interfaz text-grafito">
            {tr(
              `${data.match} terminó ${data.score}. Lo que esperaba el modelo antes del partido frente a lo que pasó: cada dato suma de −1 a +1 y 0 es lo esperado.`,
              `${data.match} ended ${data.score}. What the model expected before the match against what happened: each item adds from −1 to +1 and 0 is as expected.`,
            )}
          </p>
          {!data.has_preview ? (
            <p className="text-interfaz text-grafito">
              {tr(
                "No hay previa guardada de este partido (se guarda desde el 24-10-2026).",
                "There is no saved preview for this match (saved since 24-10-2026).",
              )}
            </p>
          ) : (
            <div className="grid gap-x-10 gap-y-5 lg:grid-cols-2">
              {data.teams.map((t) => (
                <Items key={t.team} title={t.team} score={t.score} items={t.items} />
              ))}
              {data.players.map((p) => (
                <Items key={p.name} title={`${p.name} (${p.team})`} score={p.score} items={p.items} />
              ))}
            </div>
          )}
          <div className="mt-5 max-w-[72ch] text-interfaz">
            <p className="font-bold">{tr("¿Lo avisaba Sorpresas?", "Did Surprises warn about it?")}</p>
            {data.flagged.length === 0 ? (
              <p className="text-grafito">
                {tr(
                  "No: ninguno de los dos equipos estaba en el radar cuando se generó la apuesta.",
                  "No: neither team was on the radar when the bet was generated.",
                )}
              </p>
            ) : (
              data.flagged.map((f) => (
                <p key={f.team}>
                  {f.kind === "racha"
                    ? tr(`Sí: ${f.team} estaba en racha.`, `Yes: ${f.team} was on a run.`)
                    : tr(`Sí: ${f.team} estaba en baja.`, `Yes: ${f.team} was in a slump.`)}{" "}
                  {f.reason.type === "suma"
                    ? f.kind === "racha"
                      ? tr("Venía muy por encima de lo esperado en las últimas 4 semanas.", "It had been well above expectations over the last 4 weeks.")
                      : tr("Venía muy por debajo de lo esperado en las últimas 4 semanas.", "It had been well below expectations over the last 4 weeks.")
                    : reasonText({ reason: f.reason, score: 0, n_matches: 0 })}
                  {f.figures_played.length > 0 &&
                    tr(` Jugaron sus figuras: ${f.figures_played.join(", ")}.`, ` Its key players played: ${f.figures_played.join(", ")}.`)}
                </p>
              ))
            )}
          </div>
          {data.note && <NotaClaude note={data.note} />}
        </>
      )}
    </section>
  );
}
