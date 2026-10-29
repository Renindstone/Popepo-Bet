"use client";

import { Crest } from "@/components/Crest";
import { PitchFrame, PitchName } from "@/components/Pitch";
import { Empty, ErrorNote, Loading, Section, Tag } from "@/components/ui";
import { useApi } from "@/lib/api";
import { shortName } from "@/lib/format";
import type { LineupPlayer, LineupTeam, MatchLineups } from "@/lib/types";

const KINDS: Record<string, string> = { injury: "Lesión", suspension: "Sanción", doubtful: "Duda", other: "Baja" };

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
      actions={data?.status ? <Tag tone={confirmed ? "confirmada" : "neutral"}>{confirmed ? "Confirmadas" : "Probables"}</Tag> : undefined}
    >
      {error ? (
        <ErrorNote error={error} onRetry={() => mutate()} />
      ) : !data ? (
        <Loading lines={4} label="Cargando alineaciones" />
      ) : !data.status || data.teams.every((t) => t.starters.length === 0) ? (
        <Empty>FotMob aún no publica las alineaciones probables de este partido.</Empty>
      ) : (
        <>
          <div className="mb-4 grid grid-cols-2 gap-4 text-interfaz">
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
        <Crest id={t.team_id} size={24} className="mr-2 -mt-0.5" />
        {t.team}
        <span
          className={`ml-2 inline-block size-3 rounded-full align-middle ${t.side === "home" ? "bg-ficha ring-1 ring-tinta" : "bg-negro ring-1 ring-tinta"}`}
          title={t.side === "home" ? "Blanco en el campo" : "Azul en el campo"}
          aria-hidden="true"
        />
      </p>
      <p className="text-nota text-grafito">
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
    <PitchFrame
      orientation={orientation}
      label={teams.map((t) => `${t.team} (${t.formation ?? "sin formación"}): ${t.starters.map((p) => p.name).join(", ")}`).join(". ")}
    >
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
                className={`relative flex size-8 items-center justify-center rounded-full text-nota font-bold shadow ${
                  t.side === "home" ? "bg-ficha text-negro" : "bg-negro text-amarillo ring-1 ring-white/50"
                }`}
              >
                {p.shirt ?? ""}
                {p.rating != null && (
                  <span className="absolute -top-2 -right-4 bg-negro px-1 text-xs leading-4 font-semibold text-white">
                    {p.rating.toFixed(1)}
                  </span>
                )}
              </span>
              <PitchName>{shortName(p.name)}</PitchName>
            </div>
          );
        }),
      )}
    </PitchFrame>
  );
}

function Bench({ t, confirmed }: { t: LineupTeam; confirmed: boolean }) {
  return (
    <div className="min-w-0">
      <h3 className="semi font-bold">{t.team}</h3>
      <h4 className="mt-2 text-nota font-semibold">Suplentes</h4>
      {t.subs.length === 0 ? (
        <p className="text-nota text-grafito">
          {confirmed ? "Sin suplentes publicados." : "Se conocen cuando se confirma la alineación."}
        </p>
      ) : (
        <ul className="mt-1 grid grid-cols-1 gap-x-4 text-nota sm:grid-cols-2">
          {t.subs.map((p) => (
            <li key={p.player_id} className="truncate py-0.5">
              <span className="num inline-block w-6 text-grafito">{p.shirt ?? ""}</span>
              {p.name}
              {p.position && <span className="text-grafito"> {p.position}</span>}
            </li>
          ))}
        </ul>
      )}
      <h4 className="mt-3 text-nota font-semibold">Bajas</h4>
      {t.unavailable.length === 0 ? (
        <p className="text-nota text-grafito">Ninguna registrada.</p>
      ) : (
        <ul className="mt-1 text-nota">
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
