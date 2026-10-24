"use client";

import { Crest } from "@/components/Crest";
import { PitchDisc, PitchFrame, PitchName } from "@/components/Pitch";
import { shortName, signedNum } from "@/lib/format";
import type { WeekRecap } from "@/lib/types";

// 4-3-3 en vertical, con el portero abajo (posición en % del campo)
const COORDS: Record<string, { left: number; top: number }[]> = {
  GK: [{ left: 50, top: 89 }],
  DF: [
    { left: 14, top: 69 },
    { left: 38, top: 72 },
    { left: 62, top: 72 },
    { left: 86, top: 69 },
  ],
  MF: [
    { left: 25, top: 47 },
    { left: 50, top: 50 },
    { left: 75, top: 47 },
  ],
  FW: [
    { left: 18, top: 23 },
    { left: 50, top: 18 },
    { left: 82, top: 23 },
  ],
};
const LINE_NAMES: Record<string, string> = { GK: "Portero", DF: "Defensas", MF: "Mediocampistas", FW: "Delanteros" };

/** Once de la semana: los que más superaron lo esperado en cada línea */
export function OnceSemana({ eleven }: { eleven: WeekRecap["eleven"] }) {
  const used: Record<string, number> = {};
  const placed = eleven.slots.map((sl) => {
    const i = used[sl.line] ?? 0;
    used[sl.line] = i + 1;
    return { ...sl, pos: COORDS[sl.line][i] ?? { left: 50, top: 50 } };
  });
  const byLine = Object.keys(LINE_NAMES).map((line) => ({
    line,
    players: placed.filter((sl) => sl.line === line && sl.player).map((sl) => sl.player!),
  }));
  const label = byLine
    .map((l) => `${LINE_NAMES[l.line]}: ${l.players.length ? l.players.map((p) => p.name).join(", ") : "sin jugador"}`)
    .join(". ");

  return (
    <div className="grid gap-6 md:grid-cols-[minmax(0,460px)_minmax(0,1fr)]">
      <PitchFrame orientation="vertical" label={`Once de la semana (${eleven.formation}). ${label}`}>
        {placed.map((sl, i) => (
          <div
            key={i}
            className="absolute flex w-[5.5rem] -translate-x-1/2 -translate-y-1/2 flex-col items-center"
            style={{ left: `${sl.pos.left}%`, top: `${sl.pos.top}%` }}
          >
            {sl.player ? (
              <>
                <PitchDisc>
                  <Crest id={sl.player.team_id} size={22} />
                </PitchDisc>
                <PitchName>{shortName(sl.player.name)}</PitchName>
                <PitchName>{signedNum(sl.player.score, 1)}</PitchName>
              </>
            ) : (
              <>
                <span className="size-9 rounded-full border-2 border-dashed border-white/60" aria-hidden="true" />
                <PitchName>—</PitchName>
              </>
            )}
          </div>
        ))}
      </PitchFrame>
      <dl className="space-y-3 text-interfaz">
        {byLine.map((l) => (
          <div key={l.line}>
            <dt className="text-nota font-semibold text-grafito">{LINE_NAMES[l.line]}</dt>
            <dd>
              {l.players.length === 0 ? (
                <span className="text-nota text-grafito">Aún nadie con datos suficientes.</span>
              ) : (
                <ul>
                  {l.players.map((p) => (
                    <li key={p.player_id} className="flex justify-between gap-4 py-0.5">
                      <span className="min-w-0 truncate">
                        {p.name} <span className="text-grafito">({p.team})</span>
                      </span>
                      <span className={`num shrink-0 font-semibold ${p.score > 0 ? "text-boli" : p.score < 0 ? "text-rojo" : ""}`}>
                        {signedNum(p.score)}
                      </span>
                    </li>
                  ))}
                </ul>
              )}
            </dd>
          </div>
        ))}
      </dl>
    </div>
  );
}
