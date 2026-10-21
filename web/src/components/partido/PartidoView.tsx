"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo } from "react";
import { Chart, useChartTheme } from "@/components/Chart";
import { Crest } from "@/components/Crest";
import { Empty, ErrorNote, Figure, Loading, PageTitle, Section, Tag, TriBar } from "@/components/ui";
import { useApi } from "@/lib/api";
import { int, num, odds, pct, shortDate, signedPct, stageText } from "@/lib/format";
import { betLabel, bookmakerName } from "@/lib/markets";
import type {
  LineupAdjustment,
  MatchAnalysis,
  RefereeInMatch,
  RefereeProfile,
  TeamAbsences,
  TeamContext,
} from "@/lib/types";
import { STAT_NAMES, handicapOption, overGoalsOption, scoresOption, statsShareOption } from "./charts";
import { Alineaciones } from "./Alineaciones";
import { Jugadores } from "./Jugadores";

export function PartidoView() {
  const { id } = useParams<{ id: string }>();
  const { data: a, error, mutate } = useApi<MatchAnalysis>(`/matches/${id}/analysis`);

  if (error) {
    return (
      <>
        <PageTitle title="Partido" />
        <ErrorNote error={error} onRetry={() => mutate()} />
        <p className="mt-4">
          <Link href="/partidos" className="font-semibold text-boli underline underline-offset-4">
            Ver la lista de partidos
          </Link>
        </p>
      </>
    );
  }
  if (!a) {
    return (
      <>
        <PageTitle title="Partido" sub="Analizando el partido…" />
        <Loading lines={6} label="Analizando el partido" />
      </>
    );
  }

  const [date, time] = a.kickoff_local.split(" ");
  return (
    <>
      <div className="pb-8">
        <p className="flex flex-wrap items-center gap-x-3 gap-y-1 text-grafito">
          <span className="font-semibold text-tinta">{a.competition}</span>
          <span className="num">
            {shortDate(date)}, {time}
          </span>
          <Tag tone={a.stage === "confirmed" ? "confirmada" : "neutral"}>{stageText(a.stage)}</Tag>
        </p>
        <h1 className="cond mt-2 text-[2.6rem] leading-[1.02] font-extrabold tracking-[-0.01em] sm:text-6xl">
          <Crest id={a.home_id} size={52} className="mr-3 -mt-2" />
          {a.home} <span className="font-medium text-grafito">vs</span>{" "}
          <Crest id={a.away_id} size={52} className="mr-3 -mt-2" />
          {a.away}
        </h1>
        <p className="mt-4 flex flex-wrap gap-x-6 gap-y-2">
          <Link
            href={`/evaluar?partido=${a.match_id}`}
            className="font-semibold text-boli underline underline-offset-4"
          >
            Evaluar una cuota de este partido
          </Link>
          <a href="#alineaciones" className="font-semibold text-grafito underline underline-offset-4 hover:text-tinta">
            Ver alineaciones
          </a>
          <a href="#jugadores" className="font-semibold text-grafito underline underline-offset-4 hover:text-tinta">
            Ir a jugadores
          </a>
        </p>
      </div>

      <Alineaciones matchId={a.match_id} />
      <Probabilidades a={a} />
      <Dificultad a={a} />
      <Bajas a={a} />
      <ArbitroYContexto a={a} />
      <Estadisticas a={a} />
      <ValorDelPartido a={a} />
      <Section title="Jugadores" id="jugadores" intro="Proyección para este partido según su ritmo por 90 minutos, los minutos esperados y el rival. Elige un jugador para ver sus probabilidades.">
        <Jugadores a={a} />
      </Section>
      <Calidad a={a} />
    </>
  );
}

// --------------------------------------------------------------------------- probabilidades

function Probabilidades({ a }: { a: MatchAnalysis }) {
  const t = useChartTheme();
  const m = a.model;
  const goals = useMemo(() => (t ? overGoalsOption(t, m.over_goals) : null), [t, m.over_goals]);
  const ah = useMemo(() => (t ? handicapOption(t, m.asian_handicap_home, a.home) : null), [t, m.asian_handicap_home, a.home]);
  const scores = useMemo(() => (t ? scoresOption(t, m.top_scores) : null), [t, m.top_scores]);
  const outcomes = [
    { key: "home" as const, label: a.home },
    { key: "draw" as const, label: "Empate" },
    { key: "away" as const, label: a.away },
  ];

  return (
    <Section title="Probabilidades" intro="Del modelo de goles (Dixon-Coles) con la alineación y las bajas ya aplicadas. La cuota justa es la que corresponde a esa probabilidad, sin margen de la casa.">
      <TriBar probs={m["1x2"]} home={a.home} away={a.away} size="lg" />
      <div className="mt-3 grid grid-cols-3 gap-4">
        {outcomes.map((o, i) => (
          <div key={o.key} className={i === 1 ? "text-center" : i === 2 ? "text-right" : ""}>
            <div className="cond num text-[2.6rem] leading-none font-bold">{pct(m["1x2"][o.key])}</div>
            <div className="mt-1 truncate font-semibold">{o.label}</div>
            <div className="num text-nota text-grafito">cuota justa {odds(m.fair_odds_1x2[o.key])}</div>
          </div>
        ))}
      </div>

      <div className="mt-8 grid grid-cols-2 gap-x-6 gap-y-5 border-y border-regla-suave py-5 sm:grid-cols-4">
        <Figure value={`${num(m.expected_goals.home, 2)}`} label={`goles esperados de ${a.home}`} />
        <Figure value={`${num(m.expected_goals.away, 2)}`} label={`goles esperados de ${a.away}`} />
        <Figure value={pct(m.btts_yes)} label="ambos marcan" />
        <Figure value={pct(m.over_goals["2.5"])} label="más de 2.5 goles" />
      </div>

      <div className="mt-6 grid gap-x-8 gap-y-6 lg:grid-cols-3">
        <div>
          <h3 className="semi mb-1 font-bold">Goles totales</h3>
          <Chart option={goals} height={230} label="Probabilidad de superar cada línea de goles" />
        </div>
        <div>
          <h3 className="semi mb-1 font-bold">Hándicap asiático de {a.home}</h3>
          <Chart option={ah} height={230} label={`Probabilidad de que ${a.home} cubra cada hándicap`} />
        </div>
        <div>
          <h3 className="semi mb-1 font-bold">Marcadores más probables</h3>
          <Chart option={scores} height={230} label="Marcadores exactos más probables" />
        </div>
      </div>
    </Section>
  );
}

// --------------------------------------------------------------------------- dificultad

const LEVELS = ["Difícil", "Medianamente difícil", "Parejo", "Medianamente fácil", "Fácil"];

function Dificultad({ a }: { a: MatchAnalysis }) {
  const sides = [
    { team: a.home, d: a.difficulty.home },
    { team: a.away, d: a.difficulty.away },
  ];
  return (
    <Section
      title="Dificultad del rival"
      intro="La base compara a los dos equipos al completo. La ajustada usa la alineación prevista o confirmada y las bajas de hoy."
    >
      <div className="grid gap-x-10 gap-y-8 md:grid-cols-2">
        {sides.map(({ team, d }) => (
          <div key={team}>
            <h3 className="semi text-lg font-bold">{team}</h3>
            <ol className="mt-3 grid grid-cols-5 gap-1" aria-label={`Dificultad para ${team}`}>
              {LEVELS.map((l) => {
                const isAdj = l === d.ajustada;
                const isBase = l === d.base;
                return (
                  <li key={l} className="min-w-0">
                    <div
                      className={`h-2.5 rounded-[2px] ${isAdj ? "bg-tinta" : "bg-regla"} ${
                        isBase && !isAdj ? "outline-2 outline-offset-1 outline-grafito outline-dashed" : ""
                      }`}
                    />
                    <span
                      className={`mt-1.5 hidden text-etiqueta leading-tight sm:block ${isAdj ? "font-semibold text-tinta" : "text-grafito"}`}
                    >
                      {l}
                    </span>
                  </li>
                );
              })}
            </ol>
            <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-interfaz">
              <dt className="text-grafito">Base</dt>
              <dd className="font-semibold">{d.base}</dd>
              <dt className="text-grafito">Ajustada</dt>
              <dd className="font-semibold">
                {d.ajustada}
                {d.base !== d.ajustada && <span className="font-normal text-grafito"> (antes {d.base.toLowerCase()})</span>}
              </dd>
              <dt className="text-grafito">Diferencia de goles</dt>
              <dd className="num font-semibold">{d.goal_diff > 0 ? `+${num(d.goal_diff, 2)}` : num(d.goal_diff, 2)}</dd>
            </dl>
          </div>
        ))}
      </div>
    </Section>
  );
}

// --------------------------------------------------------------------------- bajas

const KINDS: Record<string, string> = { injury: "Lesión", suspension: "Sanción", doubtful: "Duda", other: "Otro" };

function changeText(mult: number): string {
  return signedPct(mult - 1, 0);
}

function Bajas({ a }: { a: MatchAnalysis }) {
  const home = useApi<TeamAbsences>(`/teams/${encodeURIComponent(a.home)}/absences`);
  const away = useApi<TeamAbsences>(`/teams/${encodeURIComponent(a.away)}/absences`);
  const sides = [
    { team: a.home, adj: a.lineups_and_absences.home, abs: home },
    { team: a.away, adj: a.lineups_and_absences.away, abs: away },
  ];
  return (
    <Section
      title="Alineación y bajas"
      intro="Compara el once (previsto o confirmado) con el once habitual de cada equipo, ponderando valor de mercado, rating y posición."
    >
      <div className="grid gap-x-10 gap-y-10 md:grid-cols-2">
        {sides.map(({ team, adj, abs }) => (
          <div key={team} className="min-w-0">
            <h3 className="semi text-lg font-bold">{team}</h3>
            <p className="mt-0.5 text-nota text-grafito">{stageText(adj.source)}</p>
            <Ajuste adj={adj} />
            {adj.notes.length > 0 && (
              <ul className="mt-3 space-y-1 text-interfaz">
                {adj.notes.map((n) => (
                  <li key={n} className="border-l-[3px] border-tarjeta pl-3">
                    {n}
                  </li>
                ))}
              </ul>
            )}

            <h4 className="mt-5 font-semibold">Titulares habituales que faltan</h4>
            {adj.missing_regulars.length === 0 ? (
              <p className="text-interfaz text-grafito">Ninguno.</p>
            ) : (
              <ul className="mt-1 divide-y divide-regla-suave">
                {adj.missing_regulars.map((p) => (
                  <li key={p.player_id} className="flex flex-wrap items-baseline justify-between gap-x-4 py-1.5 text-interfaz">
                    <span>
                      <span className="font-semibold">{p.name}</span>
                      <span className="text-grafito"> {p.position ?? ""}</span>
                    </span>
                    <span className="text-nota text-grafito">
                      {KINDS[p.kind] ?? p.kind}, titular en el {pct(p.start_rate)}
                      {p.expected_return ? `. Vuelve: ${p.expected_return}` : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}

            <h4 className="mt-5 font-semibold">Todas las bajas activas</h4>
            {abs.error ? (
              <ErrorNote error={abs.error} />
            ) : !abs.data ? (
              <Loading lines={2} />
            ) : abs.data.absences.length === 0 ? (
              <p className="text-interfaz text-grafito">Sin bajas registradas.</p>
            ) : (
              <table className="mt-1 w-full border-collapse text-nota">
                <thead>
                  <tr className="border-b border-regla text-left text-grafito">
                    <th className="py-1.5 pr-3 font-medium">Jugador</th>
                    <th className="py-1.5 pr-3 font-medium">Motivo</th>
                    <th className="hidden py-1.5 pr-3 font-medium sm:table-cell">Vuelta</th>
                    <th className="py-1.5 text-right font-medium">Valor</th>
                  </tr>
                </thead>
                <tbody>
                  {[...abs.data.absences]
                    .sort((x, y) => y.market_value_m - x.market_value_m)
                    .map((b) => (
                      <tr key={b.player} className="border-b border-regla-suave">
                        <td className="py-1.5 pr-3">
                          {b.player}
                          {b.position && <span className="text-grafito"> {b.position}</span>}
                          {b.source === "manual" && <span className="text-grafito"> (manual)</span>}
                        </td>
                        <td className="py-1.5 pr-3">{KINDS[b.kind] ?? b.kind}</td>
                        <td className="hidden py-1.5 pr-3 text-grafito sm:table-cell">{b.expected_return ?? "—"}</td>
                        <td className="num py-1.5 text-right">{b.market_value_m ? `${num(b.market_value_m, 1)} M€` : "—"}</td>
                      </tr>
                    ))}
                </tbody>
              </table>
            )}
          </div>
        ))}
      </div>
    </Section>
  );
}

function Ajuste({ adj }: { adj: LineupAdjustment }) {
  if (adj.source === "none") return null;
  const att = adj.attack_mult - 1;
  const def = adj.defence_mult - 1;
  return (
    <dl className="mt-3 grid grid-cols-2 gap-4">
      <div>
        <dt className="text-nota text-grafito">Ataque frente a su once habitual</dt>
        <dd className={`cond num text-[1.75rem] leading-tight font-bold ${att < -0.02 ? "text-rojo" : att > 0.02 ? "text-boli" : ""}`}>
          {changeText(adj.attack_mult)}
        </dd>
      </div>
      <div>
        <dt className="text-nota text-grafito">Goles que concedería</dt>
        <dd className={`cond num text-[1.75rem] leading-tight font-bold ${def > 0.02 ? "text-rojo" : def < -0.02 ? "text-boli" : ""}`}>
          {changeText(adj.defence_mult)}
        </dd>
      </div>
    </dl>
  );
}

// --------------------------------------------------------------------------- árbitro y contexto

const PROFILE_TONE: Record<string, "rojo" | "tarjeta" | "neutral" | "boli"> = {
  "muy tarjetero": "rojo",
  tarjetero: "tarjeta",
  normal: "neutral",
  permisivo: "boli",
};

function ArbitroYContexto({ a }: { a: MatchAnalysis }) {
  return (
    <Section title="Árbitro y contexto">
      <div className="grid gap-x-10 gap-y-10 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.6fr)]">
        <Arbitro referee={a.referee} />
        <div className="grid gap-x-8 gap-y-8 sm:grid-cols-2">
          <Contexto team={a.home} c={a.context.home} />
          <Contexto team={a.away} c={a.context.away} />
        </div>
      </div>
    </Section>
  );
}

function Arbitro({ referee }: { referee: RefereeInMatch | null }) {
  const profile = useApi<RefereeProfile>(referee ? `/referees/${encodeURIComponent(referee.name)}` : null);
  if (!referee) {
    return (
      <div>
        <h3 className="semi text-lg font-bold">Árbitro</h3>
        <p className="text-grafito">Aún sin designar. Las tarjetas y faltas usan la media de la liga.</p>
      </div>
    );
  }
  const p = profile.data;
  return (
    <div>
      <h3 className="semi text-lg font-bold">Árbitro</h3>
      <p className="mt-0.5 flex flex-wrap items-center gap-2">
        <span className="font-semibold">{referee.name}</span>
        {p && <Tag tone={PROFILE_TONE[p.profile] ?? "neutral"}>{p.profile}</Tag>}
      </p>
      {referee.cards_per_match == null ? (
        <p className="mt-2 text-interfaz text-grafito">{referee.note ?? "Sin historial suficiente."}</p>
      ) : (
        <>
          <div className="mt-4 grid grid-cols-2 gap-4">
            <Figure value={num(referee.cards_per_match, 1)} label={`tarjetas por partido (esperadas ${num(referee.expected_cards_per_match, 1)})`} />
            <Figure value={num(referee.fouls_per_match, 1)} label="faltas por partido" />
            <Figure
              value={`×${num(referee.cards_factor, 2)}`}
              label="factor de tarjetas"
              tone={(referee.cards_factor ?? 1) >= 1.05 ? "rojo" : undefined}
            />
            <Figure value={`×${num(referee.fouls_factor, 2)}`} label="factor de faltas" />
          </div>
          <p className="mt-3 text-nota text-grafito">
            {int(referee.matches)} {referee.matches === 1 ? "partido" : "partidos"} en la muestra
            {referee.last_match ? `, el último el ${shortDate(referee.last_match)}` : ""}.
            {referee.matches < 5 && " Con tan pocos partidos el factor pesa poco."}
          </p>
        </>
      )}
    </div>
  );
}

const ROTATION_TONE = { baja: "neutral", media: "tarjeta", alta: "rojo" } as const;

function Contexto({ team, c }: { team: string; c: TeamContext }) {
  return (
    <div>
      <h3 className="semi text-lg font-bold">{team}</h3>
      <dl className="mt-2 grid grid-cols-[1fr_auto] gap-x-4 gap-y-1.5 text-interfaz">
        <dt className="text-grafito">Días de descanso</dt>
        <dd className="num text-right font-semibold">{c.rest_days != null ? num(c.rest_days, 1) : "—"}</dd>
        <dt className="text-grafito">Partidos en 14 días</dt>
        <dd className="num text-right font-semibold">{c.matches_last_14d}</dd>
        <dt className="text-grafito">Siguiente partido</dt>
        <dd className="num text-right font-semibold">
          {c.next_match_days != null ? `en ${num(c.next_match_days, 1)} días` : "—"}
          {c.next_match_competition && <span className="font-normal text-grafito"> ({c.next_match_competition})</span>}
        </dd>
        <dt className="text-grafito">Riesgo de rotación</dt>
        <dd className="text-right">
          <Tag tone={ROTATION_TONE[c.rotation_risk]}>{c.rotation_risk}</Tag>
        </dd>
      </dl>
      {c.notes.length > 0 && (
        <ul className="mt-3 space-y-1 text-nota text-grafito">
          {c.notes.map((n) => (
            <li key={n}>{n}</li>
          ))}
        </ul>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- estadísticas

function Estadisticas({ a }: { a: MatchAnalysis }) {
  const t = useChartTheme();
  const stats = a.model.stats;
  const option = useMemo(() => (t ? statsShareOption(t, stats, a.home, a.away) : null), [t, stats, a.home, a.away]);
  const keys = Object.keys(STAT_NAMES).filter((k) => stats[k]);
  if (keys.length === 0) return null;
  return (
    <Section
      title="Estadísticas esperadas"
      intro="Cada barra reparte la estadística entre los dos equipos; las cifras son el valor esperado. Las tarjetas y faltas ya incluyen el factor del árbitro."
    >
      <div className="flex flex-wrap gap-x-5 gap-y-1 pb-2 text-nota">
        <span className="flex items-center gap-1.5">
          <span className="size-3 rounded-[2px] bg-tinta" /> {a.home}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-3 rounded-[2px] bg-regla" /> {a.away}
        </span>
      </div>
      <Chart option={option} height={keys.length * 46 + 10} label="Reparto esperado de remates, córners, faltas y tarjetas" />

      <h3 className="semi mt-6 mb-2 font-bold">Probabilidad de superar cada línea (total del partido)</h3>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] border-collapse text-interfaz">
          <thead>
            <tr className="border-b border-regla text-left text-nota text-grafito">
              <th className="py-2 pr-4 font-medium">Estadística</th>
              <th className="py-2 pr-4 text-right font-medium">Esperado</th>
              <th className="py-2 font-medium">Más de…</th>
            </tr>
          </thead>
          <tbody>
            {keys.map((k) => (
              <tr key={k} className="border-b border-regla-suave">
                <td className="py-2 pr-4 font-semibold">{STAT_NAMES[k]}</td>
                <td className="num py-2 pr-4 text-right">{num(stats[k].expected.total, 1)}</td>
                <td className="py-2">
                  <div className="flex flex-wrap gap-x-5 gap-y-1">
                    {Object.entries(stats[k].over).map(([ln, p]) => (
                      <span key={ln} className="num whitespace-nowrap">
                        <span className="text-grafito">{ln}</span>{" "}
                        <span className={p >= 0.5 ? "font-semibold" : "text-grafito"}>{pct(p)}</span>
                      </span>
                    ))}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Section>
  );
}

// --------------------------------------------------------------------------- valor

function ValorDelPartido({ a }: { a: MatchAnalysis }) {
  const teams = { home: a.home, away: a.away };
  return (
    <Section title="Cuotas con valor y props" intro="Cuotas de bet365 y Betano con valor positivo para este partido, y la cuota mínima a pedir en los props que no tienen cuota.">
      <div className="grid gap-x-10 gap-y-8 lg:grid-cols-2">
        <div className="min-w-0">
          <h3 className="semi mb-2 font-bold">Con valor</h3>
          {a.value_bets.length === 0 ? (
            <Empty>Ninguna cuota disponible tiene valor positivo.</Empty>
          ) : (
            <table className="w-full border-collapse text-interfaz">
              <thead>
                <tr className="border-b border-regla text-left text-nota text-grafito">
                  <th className="py-2 pr-3 font-medium">Apuesta</th>
                  <th className="py-2 pr-3 text-right font-medium">Cuota</th>
                  <th className="py-2 pr-3 text-right font-medium">Estimamos</th>
                  <th className="py-2 text-right font-medium">Valor</th>
                </tr>
              </thead>
              <tbody>
                {a.value_bets.map((b, i) => (
                  <tr key={i} className="border-b border-regla-suave">
                    <td className="py-2 pr-3">
                      {b.label}
                      <span className="block text-nota text-grafito">{bookmakerName(b.bookmaker)}</span>
                    </td>
                    <td className="cond num py-2 pr-3 text-right text-lg font-bold">{odds(b.odds)}</td>
                    <td className="num py-2 pr-3 text-right">{pct(b.prob)}</td>
                    <td className="num py-2 text-right font-semibold text-boli">{signedPct(b.ev)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
        <div className="min-w-0">
          <h3 className="semi mb-2 font-bold">Props: cuota mínima</h3>
          {a.props_min_odds.length === 0 ? (
            <Empty>Sin props destacados.</Empty>
          ) : (
            <table className="w-full border-collapse text-interfaz">
              <thead>
                <tr className="border-b border-regla text-left text-nota text-grafito">
                  <th className="py-2 pr-3 font-medium">Apuesta</th>
                  <th className="py-2 pr-3 text-right font-medium">Prob.</th>
                  <th className="py-2 text-right font-medium">Cuota mínima</th>
                </tr>
              </thead>
              <tbody>
                {a.props_min_odds.slice(0, 14).map((p, i) => (
                  <tr key={i} className="border-b border-regla-suave">
                    <td className="py-2 pr-3">{betLabel(p.market, p.selection, p.line, { ...teams, player: p.player })}</td>
                    <td className="num py-2 pr-3 text-right">{pct(p.prob)}</td>
                    <td className="cond num py-2 text-right text-lg font-bold text-boli">{odds(p.min_odds)}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          )}
        </div>
      </div>
    </Section>
  );
}

// --------------------------------------------------------------------------- calidad

function Calidad({ a }: { a: MatchAnalysis }) {
  const q = a.data_quality;
  return (
    <section className="border-t border-regla pt-4 pb-6 text-nota text-grafito">
      <h2 className="sr-only">Calidad de los datos</h2>
      <p className="max-w-[80ch]">
        Calidad de los datos: {stageText(q.lineup_status).toLowerCase()} (factor {num(q.lineup_factor, 2)}), muestra
        mínima de {num(q.weighted_matches_min, 1)} partidos ponderados (factor {num(q.sample_factor, 2)}),{" "}
        {q.referee_known ? "árbitro conocido" : "árbitro sin historial"}. Modelo entrenado el {shortDate(q.model_as_of)}.
      </p>
    </section>
  );
}
