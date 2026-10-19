"use client";

import Link from "next/link";
import { Fragment, useState } from "react";
import useSWR from "swr";
import { ErrorNote, Loading } from "@/components/ui";
import { api, useApi } from "@/lib/api";
import { num, pct } from "@/lib/format";
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

const th = "py-2 pr-3 text-right text-[0.85rem] font-medium text-grafito";
const td = "num py-2 pr-3 text-right";

export function Jugadores({ a }: { a: MatchAnalysis }) {
  const sides = useTeamSides(a);
  const [filter, setFilter] = useState<"" | "home" | "away">("");
  const [open, setOpen] = useState<number | null>(null);
  const known = Object.keys(sides).length > 0;
  const rows = a.players.filter((p) => !filter || sides[p.team_id] === filter);

  if (a.players.length === 0) {
    return <p className="text-grafito">Sin proyecciones de jugadores para este partido.</p>;
  }

  return (
    <>
      {known && (
        <div className="mb-3 flex flex-wrap gap-1">
          {(
            [
              ["", "Ambos equipos"],
              ["home", a.home],
              ["away", a.away],
            ] as const
          ).map(([v, label]) => (
            <button
              key={v}
              type="button"
              aria-pressed={filter === v}
              onClick={() => setFilter(v)}
              className={`h-9 rounded-[3px] border px-3 text-[0.9rem] font-semibold ${
                filter === v ? "border-tinta bg-tinta text-papel" : "border-regla bg-hoja text-grafito hover:text-tinta"
              }`}
            >
              {label}
            </button>
          ))}
        </div>
      )}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[760px] border-collapse text-[0.95rem]">
          <thead className="border-b border-regla">
            <tr>
              <th className="py-2 pr-3 text-left text-[0.85rem] font-medium text-grafito">Jugador</th>
              <th className={th}>Remates</th>
              <th className={th}>A puerta</th>
              <th className={th}>Goles</th>
              <th className={th}>Titular</th>
              <th className={th}>Minutos</th>
              <th className={th}>Faltas</th>
              <th className={th}>Amarillas</th>
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
                      <span className="block text-[0.85rem] text-grafito">
                        {[p.position, side === "home" ? a.home : side === "away" ? a.away : null].filter(Boolean).join(", ")}
                      </span>
                    </td>
                    <td className={`${td} font-semibold`}>{num(p.expected.shots, 2)}</td>
                    <td className={td}>{num(p.expected.shots_on_target, 2)}</td>
                    <td className={td}>{num(p.expected.goals, 2)}</td>
                    <td className={td}>{pct(p.start_prob)}</td>
                    <td className={td}>{num(p.expected_minutes, 0)}</td>
                    <td className={td}>{num(p.expected.fouls_committed, 2)}</td>
                    <td className={td}>{num(p.expected.yellow_cards, 2)}</td>
                  </tr>
                  {isOpen && (
                    <tr className="border-b border-regla bg-hoja">
                      <td colSpan={8} className="px-3 pt-1 pb-5">
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
    <div className="grid grid-cols-[1fr_3rem] items-center gap-x-3 text-[0.92rem]">
      <span>{label}</span>
      <span className="num text-right font-semibold">{pct(p)}</span>
      <span className="col-span-2 mt-1 block h-1.5 rounded-full bg-regla-suave">
        <span className="block h-1.5 rounded-full bg-tinta" style={{ width: `${p * 100}%` }} />
      </span>
    </div>
  );
}

const PER90: [string, string][] = [
  ["shots", "Remates"],
  ["shots_on_target", "A puerta"],
  ["goals", "Goles"],
  ["xg", "xG"],
  ["fouls_committed", "Faltas"],
  ["yellow_cards", "Amarillas"],
];

function PlayerPanel({ name, matchId }: { name: string; matchId: number }) {
  const { data, error } = useApi<PlayerDetail>(`/players/${encodeURIComponent(name)}?match=${matchId}`);
  if (error) return <ErrorNote error={error} />;
  if (!data) return <Loading lines={3} />;
  const pr = data.projection;
  return (
    <div className="grid gap-x-10 gap-y-6 pt-3 md:grid-cols-[minmax(0,1.2fr)_minmax(0,1fr)]">
      <div>
        <h4 className="semi mb-3 font-bold">Probabilidades en este partido</h4>
        {pr ? (
          <div className="grid gap-x-6 gap-y-3 sm:grid-cols-2">
            <Meter label="Al menos 1 remate" p={pr.p_shots_over_0_5} />
            <Meter label="Al menos 2 remates" p={pr.p_shots_over_1_5} />
            <Meter label="Al menos 3 remates" p={pr.p_shots_over_2_5} />
            <Meter label="Al menos 1 a puerta" p={pr.p_sot_over_0_5} />
            <Meter label="Al menos 2 a puerta" p={pr.p_sot_over_1_5} />
            <Meter label="Marca gol" p={pr.p_goal} />
            <Meter label="Ve tarjeta" p={pr.p_card} />
          </div>
        ) : (
          <p className="text-grafito">{data.note ?? "No figura en la alineación prevista."}</p>
        )}
        <p className="mt-4">
          <Link
            href={`/evaluar?partido=${matchId}&mercado=player_shots&jugador=${encodeURIComponent(name)}`}
            className="font-semibold text-boli underline underline-offset-4"
          >
            Evaluar una cuota de {name}
          </Link>
        </p>
      </div>
      <div>
        <h4 className="semi mb-3 font-bold">Por 90 minutos esta temporada</h4>
        {data.per90 ? (
          <dl className="grid grid-cols-3 gap-x-4 gap-y-3">
            {PER90.map(([k, label]) => (
              <div key={k}>
                <dt className="text-[0.85rem] text-grafito">{label}</dt>
                <dd className="cond num text-xl font-bold">{num(data.per90?.[k], 2)}</dd>
              </div>
            ))}
          </dl>
        ) : (
          <p className="text-grafito">Sin minutos registrados.</p>
        )}
        <p className="mt-3 text-[0.88rem] text-grafito">
          {data.minutes90 != null && `Muestra de ${num(data.minutes90, 1)} partidos completos`}
          {data.starts != null && `, ${data.starts} titularidades`}
          {data.season_rating != null && `. Rating ${num(data.season_rating, 2)}`}
          {data.market_value_m ? `. Valor ${num(data.market_value_m, 1)} M€` : ""}.
        </p>
      </div>
    </div>
  );
}
