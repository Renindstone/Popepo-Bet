"use client";

import { NotaClaude } from "@/components/NotaClaude";
import { itemText } from "@/components/semana/Ranking";
import { reasonText } from "@/components/semana/Radar";
import { ErrorNote, Loading } from "@/components/ui";
import { useApi } from "@/lib/api";
import { signedNum } from "@/lib/format";
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
    <section aria-label="Por qué falló" className="mt-6 border-t-[3px] border-tinta pt-3">
      <h3 className="cond text-[1.75rem] leading-none font-black uppercase">Por qué falló</h3>
      {error ? (
        <ErrorNote error={error} onRetry={() => mutate()} />
      ) : !data ? (
        <Loading lines={3} label="Comparando la previa con lo que pasó" />
      ) : (
        <>
          <p className="mt-1 mb-4 max-w-[72ch] text-interfaz text-grafito">
            {data.match} terminó {data.score}. Lo que esperaba el modelo antes del partido frente a lo que pasó: cada dato
            suma de −1 a +1 y 0 es lo esperado.
          </p>
          {!data.has_preview ? (
            <p className="text-interfaz text-grafito">No hay previa guardada de este partido (se guarda desde el 24-10-2026).</p>
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
            <p className="font-bold">¿Lo avisaba Sorpresas?</p>
            {data.flagged.length === 0 ? (
              <p className="text-grafito">No: ninguno de los dos equipos estaba en el radar cuando se generó la apuesta.</p>
            ) : (
              data.flagged.map((f) => (
                <p key={f.team}>
                  Sí: {f.team} estaba {f.kind === "racha" ? "en racha" : "en baja"}.{" "}
                  {f.reason.type === "suma"
                    ? `Venía muy ${f.kind === "racha" ? "por encima" : "por debajo"} de lo esperado en las últimas 4 semanas.`
                    : reasonText({ reason: f.reason, score: 0, n_matches: 0 })}
                  {f.figures_played.length > 0 && ` Jugaron sus figuras: ${f.figures_played.join(", ")}.`}
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
