"use client";

import { Crest } from "@/components/Crest";
import { bookmakerName } from "@/lib/markets";
import { competitionName, signedNum } from "@/lib/format";
import type { WeekItem, WeekMatch, WeekPlayer, WeekTeam } from "@/lib/types";

export const POSITIONS: Record<string, string> = { GK: "Portero", DF: "Defensa", MF: "Mediocampista", FW: "Delantero" };

function scoreClass(n: number): string {
  return n > 0 ? "text-boli" : n < 0 ? "text-rojo" : "text-grafito";
}

/** "Córners 8 · la casa esperaba 4.8 (línea 4.5, Pinnacle)" */
export function itemText(i: WeekItem): string {
  const who = i.source === "casa" ? "la casa" : "el modelo";
  if (i.item === "result") {
    return `${i.label} ${i.actual} · ${who} esperaba ${i.expected.toFixed(1)} puntos${i.book ? ` (${bookmakerName(i.book)})` : ""}`;
  }
  const extra = [i.line != null ? `línea ${i.line}` : null, i.source === "casa" && i.book ? bookmakerName(i.book) : null]
    .filter(Boolean)
    .join(", ");
  return `${i.label} ${i.actual} · ${who} esperaba ${i.expected.toFixed(1)}${extra ? ` (${extra})` : ""}`;
}

/** Cada partido con sus datos y lo que sumó cada uno */
export function MatchItems({ matches }: { matches?: WeekMatch[] }) {
  if (!matches?.length) return null;
  return (
    <div className="mt-3 space-y-3">
      {matches.map((mt) => (
        <div key={mt.match_id}>
          <p className="text-nota font-semibold">
            {mt.label}
            {mt.minutes != null && <span className="font-normal text-grafito"> · {mt.minutes} min</span>}
            <span className={`num ml-2 ${scoreClass(mt.score)}`}>{signedNum(mt.score)}</span>
          </p>
          <ul className="mt-1 space-y-0.5 text-nota">
            {mt.items.map((i) => (
              <li key={i.item} className="flex justify-between gap-4">
                <span className="text-grafito">{itemText(i)}</span>
                <span className={`num shrink-0 font-semibold ${scoreClass(i.score)}`}>{signedNum(i.score)}</span>
              </li>
            ))}
          </ul>
        </div>
      ))}
    </div>
  );
}

/** Los 10 primeros; cada fila se abre para ver sus partidos y datos */
export function Ranking({ rows, kind }: { rows: (WeekTeam | WeekPlayer)[]; kind: "equipos" | "jugadores" }) {
  return (
    <ol className="divide-y divide-regla-suave border-y border-regla-suave">
      {rows.map((r, i) => {
        const player = "player_id" in r ? r : null;
        const teamId = player ? player.team_id : (r as WeekTeam).team_id;
        const sub = player
          ? [player.team, player.position ? POSITIONS[player.position] : null, `${player.minutes} min`].filter(Boolean).join(" · ")
          : competitionName((r as WeekTeam).competition);
        return (
          <li key={player ? player.player_id : teamId}>
            <details className="group">
              <summary className="flex min-h-12 cursor-pointer list-none items-center gap-3 py-2 [&::-webkit-details-marker]:hidden">
                <span className="num w-6 shrink-0 text-right text-nota text-grafito">{i + 1}</span>
                <Crest id={teamId} size={24} className="shrink-0" />
                <span className="min-w-0 flex-1">
                  <span className="block truncate font-semibold">{r.name}</span>
                  <span className="block truncate text-nota text-grafito">
                    {sub} · {r.n_matches === 1 ? "1 partido" : `${r.n_matches} partidos`}
                  </span>
                </span>
                <span className={`num cond shrink-0 text-xl font-bold ${scoreClass(r.score)}`}>{signedNum(r.score)}</span>
                <svg
                  aria-hidden="true"
                  viewBox="0 0 24 24"
                  className="size-4 shrink-0 text-grafito transition-transform group-open:rotate-180 motion-reduce:transition-none"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth={2}
                  strokeLinecap="round"
                  strokeLinejoin="round"
                >
                  <path d="m6 9 6 6 6-6" />
                </svg>
              </summary>
              <div className="pb-3 pl-9">
                <MatchItems matches={r.matches} />
              </div>
            </details>
          </li>
        );
      })}
      {rows.length === 0 && (
        <li className="py-4 text-nota text-grafito">
          {kind === "equipos"
            ? "Aún no hay equipos con partidos jugados y su vara de la casa esta semana."
            : "Aún no hay jugadores: hacen falta partidos jugados con la previa del modelo guardada."}
        </li>
      )}
    </ol>
  );
}
