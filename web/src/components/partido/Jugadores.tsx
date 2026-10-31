"use client";

import Link from "next/link";
import { Fragment, useState } from "react";
import useSWR from "swr";
import { UnusualTag } from "@/components/Unusual";
import { ErrorNote, Loading } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { num, pct } from "@/lib/format";
import { tr } from "@/lib/i18n";
import type { MatchAnalysis, PlayerDetail } from "@/lib/types";

/**
 * El análisis trae el id de equipo de cada jugador pero no a qué lado juega. Se resuelve
 * preguntando por un jugador de cada equipo (GET /players devuelve su equipo actual).
 */
function useTeamSides(a: MatchAnalysis): Record<number, "home" | "away"> {
  const firsts = new Map<number, string>();
  for (const p of a.players) if (!firsts.has(p.team_id)) firsts.set(p.team_id, p.name);
  const key = ["lados", a.match_id, [...firsts.keys()].join(",")];
  const { data } = useSWR(key, async () => {
    const out: Record<number, "home" | "away"> = {};
    await Promise.all(
      [...firsts.entries()].map(async ([teamId, name]) => {
        try {
          const d = await api<PlayerDetail>(`/players/${encodeURIComponent(name)}?match=${a.match_id}`);
          if (d.player === name && d.team) {
            if (d.team === a.home) out[teamId] = "home";
            else if (d.team === a.away) out[teamId] = "away";
          }
        } catch {
          // Sin equipo: la tabla se muestra igual, sin filtro por equipo
        }
      }),
    );
    return out;
  }, { revalidateOnFocus: false });
  return data ?? {};
}

const th = "py-2 pr-3 text-right text-nota font-medium text-grafito";
const td = "num py-2 pr-3 text-right";

export function Jugadores({ a }: { a: MatchAnalysis }) {
  const sides = useTeamSides(a);
  const [filter, setFilter] = useState<"" | "home" | "away">("");
  const [open, setOpen] = useState<number | null>(null);
  const known = Object.keys(sides).length > 0;
  const rows = a.players.filter((p) => !filter || sides[p.team_id] === filter);

  if (a.players.length === 0) {
    return <p className="text-grafito">{tr("Sin proyecciones de jugadores para este partido.", "No player projections for this match.")}</p>;
  }

  return (
    <>
      {known && (
        <div className="mb-3 flex flex-wrap gap-1">
          {(
            [
              ["", tr("Ambos equipos", "Both teams")],
              ["home", a.home],
              ["away", a.away],
            ] as const
          ).map(([v, label]) => (
            <button
              key={v}
              type="button"
              aria-pressed={filter === v}
              onClick={() => setFilter(v)}
              className={`h-9 border px-3 text-interfaz font-semibold ${
                filter === v ? "border-tinta bg-tinta text-papel" : "border-regla bg-hoja text-grafito hover:text-tinta"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-interfaz">
          <thead className="border-b border-regla">
            <tr>
              <th className="py-2 pr-3 text-left text-nota font-medium text-grafito">{tr("Jugador", "Player")}</th>
              <th className={th}>{tr("Remates", "Shots")}</th>
              <th className={th}>{tr("A puerta", "On target")}</th>
              <th className={th}>{tr("Goles", "Goals")}</th>
              <th className={th}>{tr("Asist.", "Assists")}</th>
              <th className={th}>{tr("Titular", "Starts")}</th>
              <th className={th}>{tr("Minutos", "Minutes")}</th>
              <th className={th}>{tr("Faltas", "Fouls")}</th>
              <th className={th}>{tr("Amarillas", "Yellows")}</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((p) => {
              const isOpen = open === p.player_id;
              const side = sides[p.team_id];
              return (
                <Fragment key={p.player_id}>
                  <tr className={`border-b border-regla-suave ${isOpen ? "bg-hoja" : ""}`}>
                    <td className="py-2 pr-3">
                      <button
                        type="button"
                        aria-expanded={isOpen}
                        onClick={() => setOpen(isOpen ? null : p.player_id)}
                        className="text-left font-semibold hover:text-boli"
                      >
                        {p.name}
                      </button>
                      <span className="block text-nota text-grafito">
                        {[p.position, side === "home" ? a.home : side === "away" ? a.away : null].filter(Boolean).join(", ")}
                      </span>
                      {p.start_prob >= 0.85 && <UnusualTag recent={p.recent_starts} />}
                    </td>
                    <td className={`${td} font-semibold`}>{num(p.expected.shots, 2)}</td>
                    <td className={td}>{num(p.expected.shots_on_target, 2)}</td>
                    <td className={td}>{num(p.expected.goals, 2)}</td>
                    <td className={td}>{num(p.expected.assists, 2)}</td>
                    <td className={td}>{pct(p.start_prob)}</td>
                    <td className={td}>{num(p.expected_minutes, 0)}</td>
                    <td className={td}>{num(p.expected.fouls_committed, 2)}</td>
                    <td className={td}>{num(p.expected.yellow_cards, 2)}</td>
                  </tr>
                  {isOpen && (
                    <tr className="border-b border-regla bg-hoja">
                      <td colSpan={9} className="px-3 pt-1 pb-5">
                        <PlayerPanel name={p.name} matchId={a.match_id} />
                      </td>
                    </tr>
                  )}
                </Fragment>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}

function Meter({ label, p }: { label: string; p: number }) {
  return (
    <div className="grid grid-cols-[1fr_3rem] items-center gap-x-3 text-nota">
      <span>{label}</span>
      <span className="num text-right font-semibold">{pct(p)}</span>
      <span className="col-span-2 mt-1 block h-1.5 rounded-full bg-regla-suave">
        <span className="block h-1.5 rounded-full bg-tinta" style={{ width: `${p * 100}%` }} />
      </span>
    </div>
  );
}

const per90 = (): [string, string][] => [
  ["shots", tr("Remates", "Shots")],
  ["shots_on_target", tr("A puerta", "On target")],
  ["goals", tr("Goles", "Goals")],
  ["xg", "xG"],
  ["assists", tr("Asistencias", "Assists")],
  ["xa", "xA"],
  ["fouls_committed", tr("Faltas", "Fouls")],
  ["yellow_cards", tr("Amarillas", "Yellows")],
];

function PlayerPanel({ name, matchId }: { name: string; matchId: number }) {
  const { data, error } = useApi<PlayerDetail>(`/players/${encodeURIComponent(name)}?match=${matchId}`);
  if (error) return <ErrorNote error={error} />;
  if (!data) return <Loading lines={3} />;
  const pr = data.projection;
  return (
    <div className="grid gap-x-10 gap-y-6 pt-3 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
      <div>
        <h4 className="semi mb-3 font-bold">{tr("Probabilidades en este partido", "Probabilities in this match")}</h4>
        {pr ? (
          <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
            <Meter label={tr("Al menos 1 remate", "At least 1 shot")} p={pr.p_shots_over_0_5} />
            <Meter label={tr("Al menos 2 remates", "At least 2 shots")} p={pr.p_shots_over_1_5} />
            <Meter label={tr("Al menos 3 remates", "At least 3 shots")} p={pr.p_shots_over_2_5} />
            <Meter label={tr("Al menos 1 a puerta", "At least 1 on target")} p={pr.p_sot_over_0_5} />
            <Meter label={tr("Al menos 2 a puerta", "At least 2 on target")} p={pr.p_sot_over_1_5} />
            <Meter label={tr("Marca gol", "Scores")} p={pr.p_goal} />
            <Meter label={tr("Da una asistencia", "Assists")} p={pr.p_assist} />
            <Meter label={tr("Marca o asiste", "Scores or assists")} p={pr.p_goal_assist} />
            <Meter label={tr("Ve tarjeta", "Gets booked")} p={pr.p_card} />
          </div>
        ) : (
          <p className="text-grafito">{data.note ?? tr("No figura en la alineación prevista.", "Not in the predicted line-up.")}</p>
        )}
        <p className="mt-4">
          <Link
            href={`/evaluar?partido=${matchId}&mercado=player_shots&jugador=${encodeURIComponent(name)}`}
            className="font-semibold text-boli underline underline-offset-4"
          >
            {tr(`Evaluar una cuota de ${name}`, `Check odds for ${name}`)}
          </Link>
        </p>
      </div>
      <div>
        <h4 className="semi mb-3 font-bold">{tr("Por 90 minutos esta temporada", "Per 90 minutes this season")}</h4>
        {data.per90 ? (
          <dl className="grid grid-cols-3 gap-x-4 gap-y-3">
            {per90().map(([k, label]) => (
              <div key={k}>
                <dt className="text-nota text-grafito">{label}</dt>
                <dd className="cond num text-xl font-bold">{num(data.per90?.[k], 2)}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-grafito">{tr("Sin minutos registrados.", "No minutes recorded.")}</p>
        )}
        <p className="mt-3 text-nota text-grafito">
          {data.minutes90 != null && tr(`Muestra de ${num(data.minutes90, 1)} partidos completos`, `Sample of ${num(data.minutes90, 1)} full matches`)}
          {data.starts != null && tr(`, ${data.starts} titularidades`, `, ${data.starts} starts`)}
          {data.season_rating != null && `. Rating ${num(data.season_rating, 2)}`}
          {data.market_value_m ? tr(`. Valor ${num(data.market_value_m, 1)} M€`, `. Value €${num(data.market_value_m, 1)}m`) : ""}.
        </p>
      </div>
    </div>
  );
}
