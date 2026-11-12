"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useMemo, useState } from "react";
import { Chart, useChartTheme } from "@/components/Chart";
import { Crest } from "@/components/Crest";
import { Tabs, useHashTab } from "@/components/Tabs";
import { AlertList } from "@/components/Avisos";
import { RivalrySection, RivalryTag } from "@/components/Rivalry";
import { Empty, ErrorNote, Figure, Loading, PageTitle, Section, Tag, TriBar } from "@/components/ui";
import { useApi } from "@/lib/api";
import { int, num, odds, pct, shortDate, signedPct, stageText } from "@/lib/format";
import { tr } from "@/lib/i18n";
import { betLabel, bookmakerName, statName } from "@/lib/markets";
import type {
  LineupAdjustment,
  MatchAnalysis,
  NearbyMatch,
  RefereeInMatch,
  RefereeProfile,
  TeamAbsences,
  TeamContext,
} from "@/lib/types";
import { STAT_KEYS, handicapOption, overGoalsOption, scoresOption, statsShareOption } from "./charts";
import { Alineaciones } from "./Alineaciones";
import { Jugadores } from "./Jugadores";

// El análisis entero medía más de 13.000 px en el celular: va en pestañas, en el orden de antes
export function PartidoView() {
  const { id } = useParams<{ id: string }>();
  const { data: a, error, mutate } = useApi<MatchAnalysis>(`/matches/${id}/analysis`);
  const TABS = [
    { id: "alineaciones", label: tr("Alineaciones", "Line-ups") },
    { id: "probabilidades", label: tr("Probabilidades", "Probabilities") },
    { id: "estadisticas", label: tr("Estadísticas", "Stats") },
    { id: "cuotas", label: tr("Cuotas", "Odds") },
    { id: "jugadores", label: tr("Jugadores", "Players") },
  ];
  const [tab, setTab] = useHashTab(TABS);

  if (error) {
    return (
      <>
        <PageTitle title={tr("Partido", "Match")} />
        <ErrorNote error={error} onRetry={() => mutate()} />
        <p className="mt-4">
          <Link href="/partidos" className="font-semibold text-boli underline underline-offset-4">
            {tr("Ver la lista de partidos", "See the list of matches")}
          </Link>
        </p>
      </>
    );
  }
  if (!a) {
    return (
      <>
        <PageTitle title={tr("Partido", "Match")} sub={tr("Analizando el partido…", "Analysing the match…")} />
        <Loading lines={6} label={tr("Analizando el partido", "Analysing the match")} />
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
          <RivalryTag name={a.rivalry?.name} />
        </p>
        <h1 className="cond mt-2 text-cifra-grande leading-[1.02] font-extrabold tracking-[-0.01em] sm:text-6xl">
          <Crest id={a.home_id} size={52} className="mr-3 -mt-2" />
          {a.home} <span className="font-medium text-grafito">vs</span>{" "}
          <Crest id={a.away_id} size={52} className="mr-3 -mt-2" />
          {a.away}
        </h1>
        <p className="mt-4">
          <Link
            href={`/evaluar?partido=${a.match_id}`}
            className="font-semibold text-boli underline underline-offset-4"
          >
            {tr("Evaluar una cuota de este partido", "Check odds for this match")}
          </Link>
        </p>
        <AlertList alerts={a.alerts} className="mt-5" />
      </div>

      <Tabs tabs={TABS} current={tab} onSelect={setTab} label={tr("Análisis del partido", "Match analysis")}>
        {tab === "alineaciones" && (
          <>
            <Alineaciones matchId={a.match_id} />
            <Bajas a={a} />
          </>
        )}
        {tab === "probabilidades" && (
          <>
            <Probabilidades a={a} />
            <Dificultad a={a} />
            <Calidad a={a} />
          </>
        )}
        {tab === "estadisticas" && (
          <>
            {a.rivalry && <RivalrySection r={a.rivalry} />}
            <Estadisticas a={a} />
            <ArbitroYContexto a={a} />
          </>
        )}
        {tab === "cuotas" && <ValorDelPartido a={a} />}
        {tab === "jugadores" && (
          <Section
            title={tr("Jugadores", "Players")}
            id="jugadores"
            intro={tr(
              "Proyección para este partido según su ritmo por 90 minutos, los minutos esperados y el rival. Elige un jugador para ver sus probabilidades.",
              "Projection for this match from each player's rate per 90 minutes, expected minutes and the opponent. Pick a player to see their probabilities.",
            )}
          >
            <Jugadores a={a} />
          </Section>
        )}
      </Tabs>
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
    { key: "draw" as const, label: tr("Empate", "Draw") },
    { key: "away" as const, label: a.away },
  ];

  return (
    <Section
      title={tr("Probabilidades", "Probabilities")}
      intro={tr(
        "Del modelo de goles (Dixon-Coles) con la alineación y las bajas ya aplicadas. La cuota justa es la que corresponde a esa probabilidad, sin margen de la casa.",
        "From the goals model (Dixon-Coles) with the line-up and absences already applied. The fair odds are the ones that match that probability, with no bookmaker margin.",
      )}
    >
      <TriBar probs={m["1x2"]} home={a.home} away={a.away} size="lg" />
      <div className="mt-3 grid grid-cols-3 gap-4">
        {outcomes.map((o, i) => (
          <div key={o.key} className={i === 1 ? "text-center" : i === 2 ? "text-right" : ""}>
            <div className="cond num text-cifra-grande leading-none font-bold">{pct(m["1x2"][o.key])}</div>
            <div className="mt-1 truncate font-semibold">{o.label}</div>
            <div className="num text-nota text-grafito">
              {tr("cuota justa", "fair odds")} {odds(m.fair_odds_1x2[o.key])}
            </div>
          </div>
        ))}
      </div>

      <div className="mt-8 grid grid-cols-2 gap-x-6 gap-y-5 border-y border-regla-suave py-5 sm:grid-cols-4">
        <Figure value={`${num(m.expected_goals.home, 2)}`} label={tr(`goles esperados de ${a.home}`, `${a.home} expected goals`)} />
        <Figure value={`${num(m.expected_goals.away, 2)}`} label={tr(`goles esperados de ${a.away}`, `${a.away} expected goals`)} />
        <Figure value={pct(m.btts_yes)} label={tr("ambos marcan", "both teams to score")} />
        <Figure value={pct(m.over_goals["2.5"])} label={tr("más de 2.5 goles", "over 2.5 goals")} />
      </div>

      <div className="mt-6 grid gap-x-8 gap-y-6 lg:grid-cols-3">
        <div>
          <h3 className="semi mb-1 font-bold">{tr("Goles totales", "Total goals")}</h3>
          <Chart option={goals} height={230} label={tr("Probabilidad de superar cada línea de goles", "Probability of going over each goals line")} />
        </div>
        <div>
          <h3 className="semi mb-1 font-bold">{tr(`Hándicap asiático de ${a.home}`, `${a.home} Asian Handicap`)}</h3>
          <Chart option={ah} height={230} label={tr(`Probabilidad de que ${a.home} cubra cada hándicap`, `Probability that ${a.home} covers each handicap`)} />
        </div>
        <div>
          <h3 className="semi mb-1 font-bold">{tr("Marcadores más probables", "Most likely scores")}</h3>
          <Chart option={scores} height={230} label={tr("Marcadores exactos más probables", "Most likely correct scores")} />
        </div>
      </div>
    </Section>
  );
}

// --------------------------------------------------------------------------- dificultad

// Niveles tal como llegan de la API (features/context.py) y su nombre en inglés
const LEVELS: [string, string][] = [
  ["Difícil", "Hard"],
  ["Medianamente difícil", "Fairly hard"],
  ["Parejo", "Even"],
  ["Medianamente fácil", "Fairly easy"],
  ["Fácil", "Easy"],
];
const levelName = (l: string) => tr(l, LEVELS.find(([es]) => es === l)?.[1] ?? l);

function Dificultad({ a }: { a: MatchAnalysis }) {
  const sides = [
    { team: a.home, d: a.difficulty.home },
    { team: a.away, d: a.difficulty.away },
  ];
  return (
    <Section
      title={tr("Dificultad del rival", "Opponent difficulty")}
      intro={tr(
        "La base compara a los dos equipos al completo. La ajustada usa la alineación prevista o confirmada y las bajas de hoy.",
        "The base rating compares both full squads. The adjusted one uses the predicted or confirmed line-up and today's absences.",
      )}
    >
      <div className="grid gap-x-10 gap-y-8 md:grid-cols-2">
        {sides.map(({ team, d }) => (
          <div key={team}>
            <h3 className="semi text-lg font-bold">{team}</h3>
            <ol className="mt-3 grid grid-cols-5 gap-1" aria-label={tr(`Dificultad para ${team}`, `Difficulty for ${team}`)}>
              {LEVELS.map(([l]) => {
                const isAdj = l === d.ajustada;
                const isBase = l === d.base;
                return (
                  <li key={l} className="min-w-0">
                    <div
                      className={`h-2.5 ${isAdj ? "bg-tinta" : "bg-regla"} ${
                        isBase && !isAdj ? "outline-2 outline-offset-1 outline-grafito outline-dashed" : ""
                      }`}
                    />
                    <span
                      className={`mt-1.5 hidden text-etiqueta leading-tight sm:block ${isAdj ? "font-semibold text-tinta" : "text-grafito"}`}
                    >
                      {levelName(l)}
                    </span>
                  </li>
                );
              })}
            </ol>
            <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-4 gap-y-1 text-interfaz">
              <dt className="text-grafito">{tr("Base", "Base")}</dt>
              <dd className="font-semibold">{levelName(d.base)}</dd>
              <dt className="text-grafito">{tr("Ajustada", "Adjusted")}</dt>
              <dd className="font-semibold">
                {levelName(d.ajustada)}
                {d.base !== d.ajustada && (
                  <span className="font-normal text-grafito">
                    {" "}
                    ({tr("antes", "was")} {levelName(d.base).toLowerCase()})
                  </span>
                )}
              </dd>
              <dt className="text-grafito">{tr("Diferencia de goles", "Goal difference")}</dt>
              <dd className="num font-semibold">{d.goal_diff > 0 ? `+${num(d.goal_diff, 2)}` : num(d.goal_diff, 2)}</dd>
            </dl>
          </div>
        ))}
      </div>
    </Section>
  );
}

// --------------------------------------------------------------------------- bajas

const KINDS: Record<string, [string, string]> = {
  injury: ["Lesión", "Injury"],
  suspension: ["Sanción", "Suspension"],
  doubtful: ["Duda", "Doubtful"],
  other: ["Otro", "Other"],
};
const kindName = (k: string) => (KINDS[k] ? tr(...KINDS[k]) : k);

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
      title={tr("Alineación y bajas", "Line-up and absences")}
      intro={tr(
        "Compara el once (previsto o confirmado) con el once habitual de cada equipo, ponderando valor de mercado, rating y posición.",
        "Compares the XI (predicted or confirmed) with each team's usual XI, weighting market value, rating and position.",
      )}
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
                  <li key={n} className="border-l border-tarjeta pl-3">
                    {n}
                  </li>
                ))}
              </ul>
            )}

            <h4 className="mt-5 font-semibold">{tr("Titulares habituales que faltan", "Regular starters missing")}</h4>
            {adj.missing_regulars.length === 0 ? (
              <p className="text-interfaz text-grafito">{tr("Ninguno.", "None.")}</p>
            ) : (
              <ul className="mt-1 divide-y divide-regla-suave">
                {adj.missing_regulars.map((p) => (
                  <li key={p.player_id} className="flex flex-wrap items-baseline justify-between gap-x-4 py-1.5 text-interfaz">
                    <span>
                      <span className="font-semibold">{p.name}</span>
                      <span className="text-grafito"> {p.position ?? ""}</span>
                    </span>
                    <span className="text-nota text-grafito">
                      {kindName(p.kind)}, {tr("titular en el", "starts")} {pct(p.start_rate)}
                      {p.expected_return ? tr(`. Vuelve: ${p.expected_return}`, `. Back: ${p.expected_return}`) : ""}
                    </span>
                  </li>
                ))}
              </ul>
            )}

            <h4 className="mt-5 font-semibold">{tr("Todas las bajas activas", "All current absences")}</h4>
            {abs.error ? (
              <ErrorNote error={abs.error} />
            ) : !abs.data ? (
              <Loading lines={2} />
            ) : abs.data.absences.length === 0 ? (
              <p className="text-interfaz text-grafito">{tr("Sin bajas registradas.", "No absences recorded.")}</p>
            ) : (
              <table className="mt-1 w-full border-collapse text-nota">
                <thead>
                  <tr className="border-b border-regla text-left text-grafito">
                    <th className="py-1.5 pr-3 font-medium">{tr("Jugador", "Player")}</th>
                    <th className="py-1.5 pr-3 font-medium">{tr("Motivo", "Reason")}</th>
                    <th className="hidden py-1.5 pr-3 font-medium sm:table-cell">{tr("Vuelta", "Back")}</th>
                    <th className="py-1.5 text-right font-medium">{tr("Valor", "Value")}</th>
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
                        <td className="py-1.5 pr-3">{kindName(b.kind)}</td>
                        <td className="hidden py-1.5 pr-3 text-grafito sm:table-cell">{b.expected_return ?? "—"}</td>
                        <td className="num py-1.5 text-right">
                          {b.market_value_m ? tr(`${num(b.market_value_m, 1)} M€`, `€${num(b.market_value_m, 1)}m`) : "—"}
                        </td>
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
        <dt className="text-nota text-grafito">{tr("Ataque frente a su once habitual", "Attack against their usual XI")}</dt>
        <dd className={`cond num text-lateral leading-tight font-bold ${att < -0.02 ? "text-rojo" : att > 0.02 ? "text-boli" : ""}`}>
          {changeText(adj.attack_mult)}
        </dd>
      </div>
      <div>
        <dt className="text-nota text-grafito">{tr("Goles que concedería", "Goals they would concede")}</dt>
        <dd className={`cond num text-lateral leading-tight font-bold ${def > 0.02 ? "text-rojo" : def < -0.02 ? "text-boli" : ""}`}>
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
const PROFILE_EN: Record<string, string> = {
  "muy tarjetero": "very card-happy",
  tarjetero: "card-happy",
  normal: "average",
  permisivo: "lenient",
};

function ArbitroYContexto({ a }: { a: MatchAnalysis }) {
  return (
    <Section title={tr("Árbitro y contexto", "Referee and context")}>
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
        <h3 className="semi text-lg font-bold">{tr("Árbitro", "Referee")}</h3>
        <p className="text-grafito">
          {tr("Aún sin designar. Las tarjetas y faltas usan la media de la liga.", "Not appointed yet. Cards and fouls use the league average.")}
        </p>
      </div>
    );
  }
  const p = profile.data;
  return (
    <div>
      <h3 className="semi text-lg font-bold">{tr("Árbitro", "Referee")}</h3>
      <p className="mt-0.5 flex flex-wrap items-center gap-2">
        <span className="font-semibold">{referee.name}</span>
        {p && <Tag tone={PROFILE_TONE[p.profile] ?? "neutral"}>{tr(p.profile, PROFILE_EN[p.profile] ?? p.profile)}</Tag>}
      </p>
      {referee.cards_per_match == null ? (
        <p className="mt-2 text-interfaz text-grafito">{referee.note ?? tr("Sin historial suficiente.", "Not enough history.")}</p>
      ) : (
        <>
          <div className="mt-4 grid grid-cols-2 gap-4">
            <Figure
              value={num(referee.cards_per_match, 1)}
              label={tr(
                `tarjetas por partido (esperadas ${num(referee.expected_cards_per_match, 1)})`,
                `cards per match (expected ${num(referee.expected_cards_per_match, 1)})`,
              )}
            />
            <Figure value={num(referee.fouls_per_match, 1)} label={tr("faltas por partido", "fouls per match")} />
            <Figure
              value={`×${num(referee.cards_factor, 2)}`}
              label={tr("factor de tarjetas", "cards factor")}
              tone={(referee.cards_factor ?? 1) >= 1.05 ? "rojo" : undefined}
            />
            <Figure value={`×${num(referee.fouls_factor, 2)}`} label={tr("factor de faltas", "fouls factor")} />
          </div>
          <p className="mt-3 text-nota text-grafito">
            {int(referee.matches)}{" "}
            {referee.matches === 1 ? tr("partido en la muestra", "match in the sample") : tr("partidos en la muestra", "matches in the sample")}
            {referee.last_match ? tr(`, el último el ${shortDate(referee.last_match)}`, `, the latest on ${shortDate(referee.last_match)}`) : ""}.
            {referee.matches < 5 && tr(" Con tan pocos partidos el factor pesa poco.", " With so few matches the factor carries little weight.")}
          </p>
        </>
      )}
    </div>
  );
}

const ROTATION_TONE = { baja: "neutral", media: "tarjeta", alta: "rojo" } as const;
const ROTATION_EN = { baja: "low", media: "medium", alta: "high" } as const;

/** «Barcelona, en 3,0 días · Champions»: el rival de antes o de después y si es grande en su competición */
function Nearby({ g, when }: { g?: NearbyMatch | null; when: "hace" | "en" }) {
  if (!g) return <span className="font-semibold">—</span>;
  return (
    <>
      <span className="font-semibold">{g.opponent}</span>
      <span className="num text-grafito">
        ,{" "}
        {when === "hace"
          ? tr(`hace ${num(g.days, 1)} días`, `${num(g.days, 1)} days ago`)
          : tr(`en ${num(g.days, 1)} días`, `in ${num(g.days, 1)} days`)}
      </span>
      {(g.tier === "grande" || g.tier === "Champions") && (
        <Tag tone="neutral" className="ml-1.5 align-middle">
          {g.tier === "Champions" ? "Champions" : tr("grande", "big club")}
        </Tag>
      )}
    </>
  );
}

function Contexto({ team, c }: { team: string; c: TeamContext }) {
  return (
    <div>
      <h3 className="semi text-lg font-bold">{team}</h3>
      <dl className="mt-2 grid grid-cols-[auto_minmax(0,1fr)] gap-x-4 gap-y-1.5 text-interfaz">
        <dt className="text-grafito">{tr("Días de descanso", "Rest days")}</dt>
        <dd className="num text-right font-semibold">{c.rest_days != null ? num(c.rest_days, 1) : "—"}</dd>
        <dt className="text-grafito">{tr("Partidos en 14 días", "Matches in 14 days")}</dt>
        <dd className="num text-right font-semibold">{c.matches_last_14d}</dd>
        <dt className="text-grafito">{tr("Partido anterior", "Previous match")}</dt>
        <dd className="text-right">
          <Nearby g={c.prev_match} when="hace" />
        </dd>
        <dt className="text-grafito">{tr("Siguiente partido", "Next match")}</dt>
        <dd className="text-right">
          {c.next_match ? (
            <Nearby g={c.next_match} when="en" />
          ) : (
            <span className="num font-semibold">
              {c.next_match_days != null ? tr(`en ${num(c.next_match_days, 1)} días`, `in ${num(c.next_match_days, 1)} days`) : "—"}
            </span>
          )}
        </dd>
        <dt className="text-grafito">{tr("Riesgo de rotación", "Rotation risk")}</dt>
        <dd className="text-right">
          <Tag tone={ROTATION_TONE[c.rotation_risk]}>{tr(c.rotation_risk, ROTATION_EN[c.rotation_risk] ?? c.rotation_risk)}</Tag>
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
  const keys = STAT_KEYS.filter((k) => stats[k]);
  if (keys.length === 0) return null;
  return (
    <Section
      title={tr("Estadísticas esperadas", "Expected stats")}
      intro={tr(
        "Cada barra reparte la estadística entre los dos equipos; las cifras son el valor esperado. Las tarjetas y faltas ya incluyen el factor del árbitro.",
        "Each bar splits the stat between the two teams; the figures are the expected value. Cards and fouls already include the referee factor.",
      )}
    >
      <div className="flex flex-wrap gap-x-5 gap-y-1 pb-2 text-nota">
        <span className="flex items-center gap-1.5">
          <span className="size-3 bg-tinta" /> {a.home}
        </span>
        <span className="flex items-center gap-1.5">
          <span className="size-3 bg-regla" /> {a.away}
        </span>
      </div>
      <Chart
        option={option}
        height={keys.length * 46 + 10}
        label={tr("Reparto esperado de remates, córners, faltas y tarjetas", "Expected split of shots, corners, fouls and cards")}
      />

      <h3 className="semi mt-6 mb-2 font-bold">
        {tr("Probabilidad de superar cada línea (total del partido)", "Probability of going over each line (match total)")}
      </h3>
      <div className="overflow-x-auto">
        <table className="w-full min-w-[560px] border-collapse text-interfaz">
          <thead>
            <tr className="border-b border-regla text-left text-nota text-grafito">
              <th className="py-2 pr-4 font-medium">{tr("Estadística", "Stat")}</th>
              <th className="py-2 pr-4 text-right font-medium">{tr("Esperado", "Expected")}</th>
              <th className="py-2 font-medium">{tr("Más de…", "Over…")}</th>
            </tr>
          </thead>
          <tbody>
            {keys.map((k) => (
              <tr key={k} className="border-b border-regla-suave">
                <td className="py-2 pr-4 font-semibold">{statName(k)}</td>
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
  const [all, setAll] = useState(false);
  const bets = all ? a.value_bets : a.value_bets.slice(0, 12);
  return (
    <Section
      title={tr("Cuotas con valor y props", "Value odds and props")}
      intro={tr(
        "Cuotas de bet365 y Betano con valor positivo y 60 % o más de probabilidad para este partido, y la cuota mínima a pedir en los props que no tienen cuota.",
        "bet365 and Betano odds with positive value and a 60% or higher probability for this match, and the minimum odds to ask for on props that have no price.",
      )}
    >
      <div className="grid gap-x-10 gap-y-8 lg:grid-cols-2">
        <div className="min-w-0">
          <h3 className="semi mb-2 font-bold">{tr("Con valor", "With value")}</h3>
          {a.value_bets.length === 0 ? (
            <Empty>{tr("Ninguna cuota disponible tiene valor positivo y 60 % o más de probabilidad.", "No available odds have positive value and a 60% or higher probability.")}</Empty>
          ) : (
            <table className="w-full border-collapse text-interfaz">
              <thead>
                <tr className="border-b border-regla text-left text-nota text-grafito">
                  <th className="py-2 pr-3 font-medium">{tr("Apuesta", "Bet")}</th>
                  <th className="py-2 pr-3 text-right font-medium">{tr("Cuota", "Odds")}</th>
                  <th className="py-2 pr-3 text-right font-medium">{tr("Estimamos", "We estimate")}</th>
                  <th className="py-2 text-right font-medium">{tr("Valor", "Value")}</th>
                </tr>
              </thead>
              <tbody>
                {bets.map((b, i) => (
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
          {a.value_bets.length > 12 && (
            <button
              type="button"
              onClick={() => setAll(!all)}
              className="mt-1 inline-flex min-h-10 items-center text-interfaz font-semibold text-boli underline underline-offset-4"
            >
              {all ? tr("Mostrar menos", "Show fewer") : tr(`Mostrar las ${a.value_bets.length}`, `Show all ${a.value_bets.length}`)}
            </button>
          )}
        </div>
        <div className="min-w-0">
          <h3 className="semi mb-2 font-bold">{tr("Props: cuota mínima", "Props: minimum odds")}</h3>
          {a.props_min_odds.length === 0 ? (
            <Empty>{tr("Sin props destacados.", "No standout props.")}</Empty>
          ) : (
            <table className="w-full border-collapse text-interfaz">
              <thead>
                <tr className="border-b border-regla text-left text-nota text-grafito">
                  <th className="py-2 pr-3 font-medium">{tr("Apuesta", "Bet")}</th>
                  <th className="py-2 pr-3 text-right font-medium">{tr("Prob.", "Prob.")}</th>
                  <th className="py-2 text-right font-medium">{tr("Cuota mínima", "Minimum odds")}</th>
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
      <h2 className="sr-only">{tr("Calidad de los datos", "Data quality")}</h2>
      <p className="max-w-[80ch]">
        {tr(
          `Calidad de los datos: ${stageText(q.lineup_status).toLowerCase()} (factor ${num(q.lineup_factor, 2)}), muestra mínima de ${num(q.weighted_matches_min, 1)} partidos ponderados (factor ${num(q.sample_factor, 2)}), ${q.referee_known ? "árbitro conocido" : "árbitro sin historial"}. Modelo entrenado el ${shortDate(q.model_as_of)}.`,
          `Data quality: ${stageText(q.lineup_status).toLowerCase()} (factor ${num(q.lineup_factor, 2)}), minimum sample of ${num(q.weighted_matches_min, 1)} weighted matches (factor ${num(q.sample_factor, 2)}), ${q.referee_known ? "referee known" : "referee without history"}. Model trained on ${shortDate(q.model_as_of)}.`,
        )}
      </p>
      {q.no_picks_note && <p className="max-w-[80ch] pt-2 font-semibold text-tinta">{q.no_picks_note}</p>}
    </section>
  );
}
