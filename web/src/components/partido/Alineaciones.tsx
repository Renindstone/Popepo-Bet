"use client";

import { Empty, ErrorNote, Loading, Section, Tag } from "@/components/ui";
import { useApi } from "@/lib/api";
import type { LineupPlayer, LineupTeam, MatchLineups } from "@/lib/types";

const KINDS: Record<string, string> = { injury: "Lesión", suspension: "Sanción", doubtful: "Duda", other: "Baja" };

/** "Vinícius Júnior" → "Vinícius Jr."; "Kylian Mbappé" → "Mbappé" (como en FotMob, el apellido) */
function shortName(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return name;
  const last = parts[parts.length - 1];
  if (/^(júnior|junior|jr\.?)$/i.test(last)) return `${parts[parts.length - 2]} Jr.`;
  return last;
}

function minutesToKickoff(kickoffLocal: string): number {
  // "YYYY-MM-DD HH:MM" en hora de Lima (UTC−5, sin horario de verano)
  const [d, t] = kickoffLocal.split(" ");
  return (Date.parse(`${d}T${t}:00-05:00`) - Date.now()) / 60000;
}

/** Alineaciones como en FotMob: probables hasta que se confirman, en el campo y con suplentes y bajas. */
export function Alineaciones({ matchId }: { matchId: number }) {
  // Cerca del partido y sin confirmar, se vuelve a pedir cada 5 minutos para que aparezca la confirmada
  const { data, error, mutate } = useApi<MatchLineups>(`/matches/${matchId}/lineups`, {
    refreshInterval: (d) => (d && d.status !== "confirmed" && minutesToKickoff(d.kickoff_local) < 120 ? 300_000 : 0),
  });

  const confirmed = data?.status === "confirmed";
  return (
    <Section
      title="Alineaciones"
      id="alineaciones"
      intro={
        !data?.status
          ? undefined
          : confirmed
            ? `Confirmadas. Actualizado ${data.updated_local?.slice(11) ?? ""}.`
            : "Probables, según FotMob. La confirmada se busca 70, 50, 35, 20 y 10 minutos antes del inicio (suele salir una hora antes)."
      }
      actions={data?.status ? <Tag tone={confirmed ? "boli" : "neutral"}>{confirmed ? "Confirmadas" : "Probables"}</Tag> : undefined}
    >
      {error ? (
        <ErrorNote error={error} onRetry={() => mutate()} />
      ) : !data ? (
        <Loading lines={4} label="Cargando alineaciones" />
      ) : !data.status || data.teams.every((t) => t.starters.length === 0) ? (
        <Empty>FotMob aún no publica las alineaciones probables de este partido.</Empty>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-4 text-[0.95rem]">
            {data.teams.map((t) => (
              <TeamHeader key={t.side} t={t} />
            ))}
          </div>
          <div className="hidden md:block">
            <Pitch teams={data.teams} orientation="horizontal" />
          </div>
          <div className="md:hidden">
            <Pitch teams={data.teams} orientation="vertical" />
          </div>
          <div className="mt-6 grid gap-x-10 gap-y-6 md:grid-cols-2">
            {data.teams.map((t) => (
              <Bench key={t.side} t={t} confirmed={confirmed} />
            ))}
          </div>
        </>
      )}
    </Section>
  );
}

function TeamHeader({ t }: { t: LineupTeam }) {
  return (
    <div className={t.side === "away" ? "text-right" : ""}>
      <p className="semi font-bold">
        <span className={`mr-2 inline-block size-3 rounded-full align-middle ${t.side === "home" ? "bg-hoja ring-1 ring-tinta" : "bg-boli"}`} aria-hidden="true" />
        {t.team}
      </p>
      <p className="text-[0.88rem] text-grafito">
        {[t.formation, t.coach && `Entrenador: ${t.coach}`].filter(Boolean).join(" · ")}
      </p>
    </div>
  );
}

/**
 * Campo con los dos equipos. FotMob da la posición de cada titular en vista vertical (0-1, desde su portería).
 * Horizontal: el local ataca hacia la derecha y el visitante hacia la izquierda; vertical: el local arriba.
 */
function Pitch({ teams, orientation }: { teams: LineupTeam[]; orientation: "horizontal" | "vertical" }) {
  const horizontal = orientation === "horizontal";
  const place = (side: LineupTeam["side"], p: LineupPlayer) => {
    const x = p.x ?? 0.5;
    const y = p.y ?? 0.5;
    if (horizontal) {
      return side === "home" ? { left: y * 50, top: (1 - x) * 100 } : { left: 100 - y * 50, top: x * 100 };
    }
    return side === "home" ? { left: x * 100, top: y * 50 } : { left: (1 - x) * 100, top: 100 - y * 50 };
  };
  return (
    <div
      className={`relative w-full overflow-hidden rounded-[6px] bg-[#2e5d45] ${horizontal ? "aspect-[105/68]" : "mx-auto aspect-[68/105] max-w-[460px]"}`}
      role="img"
      aria-label={teams.map((t) => `${t.team} (${t.formation ?? "sin formación"}): ${t.starters.map((p) => p.name).join(", ")}`).join(". ")}
    >
      <PitchLines horizontal={horizontal} />
      {teams.flatMap((t) =>
        t.starters.map((p) => {
          const pos = place(t.side, p);
          return (
            <div
              key={`${t.side}-${p.player_id}`}
              className="absolute flex w-[5.5rem] -translate-x-1/2 -translate-y-1/2 flex-col items-center"
              style={{ left: `${pos.left}%`, top: `${pos.top}%` }}
            >
              <span
                className={`relative flex size-8 items-center justify-center rounded-full text-[0.85rem] font-bold shadow ${
                  t.side === "home" ? "bg-[#f4f6f2] text-[#1c2624]" : "bg-[#2643c4] text-white"
                }`}
              >
                {p.shirt ?? ""}
                {p.rating != null && (
                  <span className="absolute -top-2 -right-4 rounded-[3px] bg-[#1c2624]/85 px-1 text-[0.62rem] leading-4 font-semibold text-white">
                    {p.rating.toFixed(1)}
                  </span>
                )}
              </span>
              <span className="mt-0.5 max-w-full truncate rounded-[3px] bg-[#1c2624]/55 px-1 text-center text-[0.72rem] leading-4 font-medium text-white">
                {shortName(p.name)}
              </span>
            </div>
          );
        }),
      )}
    </div>
  );
}

function PitchLines({ horizontal }: { horizontal: boolean }) {
  const line = "absolute border-white/45";
  return (
    <div aria-hidden="true" className="absolute inset-[3%]">
      <div className={`${line} inset-0 border-2`} />
      {horizontal ? (
        <>
          <div className={`${line} top-0 bottom-0 left-1/2 border-l-2`} />
          <div className={`${line} top-1/2 left-1/2 aspect-square h-[27%] -translate-x-1/2 -translate-y-1/2 rounded-full border-2`} />
          <div className={`${line} top-[21%] bottom-[21%] left-0 w-[16%] border-2 border-l-0`} />
          <div className={`${line} top-[21%] right-0 bottom-[21%] w-[16%] border-2 border-r-0`} />
          <div className={`${line} top-[37%] bottom-[37%] left-0 w-[5.5%] border-2 border-l-0`} />
          <div className={`${line} top-[37%] right-0 bottom-[37%] w-[5.5%] border-2 border-r-0`} />
        </>
      ) : (
        <>
          <div className={`${line} top-1/2 right-0 left-0 border-t-2`} />
          <div className={`${line} top-1/2 left-1/2 aspect-square w-[27%] -translate-x-1/2 -translate-y-1/2 rounded-full border-2`} />
          <div className={`${line} top-0 right-[21%] left-[21%] h-[16%] border-2 border-t-0`} />
          <div className={`${line} right-[21%] bottom-0 left-[21%] h-[16%] border-2 border-b-0`} />
          <div className={`${line} top-0 right-[37%] left-[37%] h-[5.5%] border-2 border-t-0`} />
          <div className={`${line} right-[37%] bottom-0 left-[37%] h-[5.5%] border-2 border-b-0`} />
        </>
      )}
    </div>
  );
}

function Bench({ t, confirmed }: { t: LineupTeam; confirmed: boolean }) {
  return (
    <div className="min-w-0">
      <h3 className="semi font-bold">{t.team}</h3>
      <h4 className="mt-2 text-[0.9rem] font-semibold">Suplentes</h4>
      {t.subs.length === 0 ? (
        <p className="text-[0.9rem] text-grafito">
          {confirmed ? "Sin suplentes publicados." : "Se conocen cuando se confirma la alineación."}
        </p>
      ) : (
        <ul className="mt-1 grid grid-cols-1 gap-x-4 text-[0.92rem] sm:grid-cols-2">
          {t.subs.map((p) => (
            <li key={p.player_id} className="truncate py-0.5">
              <span className="num inline-block w-6 text-grafito">{p.shirt ?? ""}</span>
              {p.name}
              {p.position && <span className="text-grafito"> {p.position}</span>}
            </li>
          ))}
        </ul>
      )}
      <h4 className="mt-3 text-[0.9rem] font-semibold">Bajas</h4>
      {t.unavailable.length === 0 ? (
        <p className="text-[0.9rem] text-grafito">Ninguna registrada.</p>
      ) : (
        <ul className="mt-1 text-[0.92rem]">
          {t.unavailable.map((u) => (
            <li key={u.name} className="py-0.5">
              {u.name}
              <span className="text-grafito">
                {" "}
                · {KINDS[u.kind] ?? u.kind}
                {u.reason && u.reason.toLowerCase() !== u.kind ? ` (${u.reason})` : ""}
                {u.expected_return ? `. Vuelve: ${u.expected_return}` : ""}
              </span>
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
