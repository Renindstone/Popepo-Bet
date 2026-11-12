"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Crest } from "@/components/Crest";
import { MatchItems, positionName, Ranking } from "@/components/semana/Ranking";
import { OnceSemana } from "@/components/semana/OnceSemana";
import { Radar } from "@/components/semana/Radar";
import { Tabs, useHashTab } from "@/components/Tabs";
import { Empty, ErrorNote, Figure, Loading, PageTitle, Section } from "@/components/ui";
import { useApi } from "@/lib/api";
import { competitionName, monthAvailableFrom, rangeLabel, shiftDay, shortDate, signedNum, weekStart } from "@/lib/format";
import { useToday } from "@/lib/hooks";
import { tr } from "@/lib/i18n";
import type { PeriodRecap, WeekPlayer, WeekRecap, WeekTeam } from "@/lib/types";

const navLink =
  "inline-flex h-10 items-center border border-tinta bg-hoja px-3 text-interfaz font-bold transition-colors hover:bg-tinta hover:text-papel";
const pickerOn = "inline-flex h-10 items-center border border-tinta bg-tinta px-4 text-interfaz font-bold text-papel";
const pickerOff =
  "inline-flex h-10 items-center border border-tinta bg-hoja px-4 text-interfaz font-bold transition-colors hover:bg-tinta hover:text-papel";

/** Sorpresas: quién superó lo que esperaban la casa (equipos) y el modelo (jugadores), por semana o por mes */
export function SemanaView() {
  const params = useSearchParams();
  const today = useToday();
  const month = params.get("periodo") === "mes";
  const current = today ? weekStart(today) : "";
  const asked = params.get("semana");
  const monday = asked ? weekStart(asked) : current;
  const path = month ? (asked ? `/week?period=mes&day=${monday}` : "/week?period=mes") : monday ? `/week?day=${monday}` : null;
  const { data, error, mutate } = useApi<PeriodRecap>(path);
  // El mes se identifica por su última semana; sin ?semana= es la última completa
  const last = data ? weekStart(data.week_end) : monday;
  const lastFull = current ? shiftDay(current, -7) : "";
  const step = month ? 28 : 7;
  const recap = data?.available ? data : null;
  const tabs = [
    { id: "once", label: month ? tr("Once del mes", "Team of the month") : tr("Once de la semana", "Team of the week") },
    { id: "equipos", label: tr("Equipos", "Teams"), count: recap?.teams.length },
    { id: "jugadores", label: tr("Jugadores", "Players"), count: recap?.players.length },
  ];
  const [tab, setTab] = useHashTab(tabs);
  const keep = tab !== tabs[0].id ? `#${tab}` : "";
  const href = (week: string | null) =>
    `/sorpresas?${[month ? "periodo=mes" : null, week ? `semana=${week}` : null].filter(Boolean).join("&")}${keep}`;
  const newest = month ? lastFull : current;

  const nav = last && (
    <>
      <Link href={href(shiftDay(last, -step))} className={navLink}>
        {month ? tr("Mes anterior", "Previous month") : tr("Semana anterior", "Previous week")}
      </Link>
      {last < newest && (
        <Link href={href(shiftDay(last, step))} className={navLink}>
          {month ? tr("Mes siguiente", "Next month") : tr("Semana siguiente", "Next week")}
        </Link>
      )}
      {last !== newest && (
        <Link href={href(null)} className="inline-flex h-10 items-center px-2 text-interfaz font-bold text-boli underline underline-offset-4">
          {month ? tr("Volver al último mes", "Back to the latest month") : tr("Volver a esta semana", "Back to this week")}
        </Link>
      )}
    </>
  );
  const label = data ? rangeLabel(data.week_start, data.week_end) : "";
  const monthFrom = monthAvailableFrom(recap?.history_since);
  const monthLocked = !month && !!today && (!monthFrom || today < monthFrom);

  return (
    <>
      <PageTitle
        title={tr("Sorpresas", "Surprises")}
        sub={
          label
            ? `${label.charAt(0).toUpperCase()}${label.slice(1)}${recap?.status === "en_curso" ? tr(", en curso", ", in progress") : ""}.`
            : null
        }
        actions={nav}
      />
      <div role="group" aria-label={tr("Periodo", "Period")} className="-mt-2 mb-6 flex flex-wrap items-center gap-2">
        {month ? (
          <Link href="/sorpresas" className={pickerOff}>
            {tr("Semana", "Week")}
          </Link>
        ) : (
          <span aria-current="page" className={pickerOn}>
            {tr("Semana", "Week")}
          </span>
        )}
        {month ? (
          <span aria-current="page" className={pickerOn}>
            {tr("Mes", "Month")}
          </span>
        ) : monthLocked ? (
          <span className="inline-flex h-10 items-center border border-regla px-4 text-interfaz font-bold text-grafito">
            {monthFrom
              ? tr(`Mes · desde el ${shortDate(monthFrom)}`, `Month · from ${shortDate(monthFrom)}`)
              : tr("Mes · cuando haya 4 semanas", "Month · once there are 4 weeks")}
          </span>
        ) : (
          <Link href="/sorpresas?periodo=mes" className={pickerOff}>
            {tr("Mes", "Month")}
          </Link>
        )}
        <span className="text-nota text-grafito">
          {tr("El mes son las 4 semanas completas que terminan en la elegida.", "The month is the 4 full weeks ending with the chosen one.")}
        </span>
      </div>
      {error ? (
        <div className="pb-10">
          <ErrorNote error={error} onRetry={() => mutate()} />
        </div>
      ) : !data ? (
        <div className="pb-10">
          <Loading lines={6} label={tr("Calculando las sorpresas", "Working out the surprises")} />
        </div>
      ) : !data.available ? (
        <>
          <p className="mb-8 max-w-[72ch] border-t-[3px] border-tarjeta bg-tarjeta-suave px-3 py-2 text-interfaz">
            {data.available_from
              ? tr(
                  `El mes llega el ${shortDate(data.available_from)}: hacen falta 4 semanas completas con la previa del modelo guardada.`,
                  `The month arrives on ${shortDate(data.available_from)}: it needs 4 full weeks with the model's preview saved.`,
                )
              : tr(
                  "El mes llegará cuando haya 4 semanas completas con la previa del modelo guardada.",
                  "The month will arrive once there are 4 full weeks with the model's preview saved.",
                )}
          </p>
          <Radar />
        </>
      ) : (
        <RecapBody data={data} month={month} tabs={tabs} tab={tab} setTab={setTab} />
      )}
    </>
  );
}

function RecapBody({
  data,
  month,
  tabs,
  tab,
  setTab,
}: {
  data: WeekRecap;
  month: boolean;
  tabs: { id: string; label: string; count?: number }[];
  tab: string;
  setTab: (id: string) => void;
}) {
  return (
        <>
          <p className="mb-3 max-w-[72ch] border-t-[3px] border-tarjeta bg-tarjeta-suave px-3 py-2 text-interfaz">{data.note}</p>
          <Coverage data={data} />
          {data.coverage.played === 0 ? (
            <>
              <div className="pb-8">
                <Empty>
                  {month
                    ? tr("En este mes aún no se jugó ningún partido de las diez competiciones.", "No match from the ten competitions has been played this month yet.")
                    : tr("Esta semana aún no se jugó ningún partido de las diez competiciones.", "No match from the ten competitions has been played this week yet.")}
                </Empty>
              </div>
              {/* El radar mira los últimos 28 días: no depende de que la semana elegida tenga partidos */}
              <Radar />
            </>
          ) : (
            <>
              <div className="grid gap-x-10 gap-y-8 pb-8 lg:grid-cols-2">
                <Destacado kind="equipo" month={month} row={data.team_of_week} />
                <Destacado kind="jugador" month={month} row={data.player_of_week} />
              </div>
              <Radar />
              <Tabs
                tabs={tabs}
                current={tab}
                onSelect={setTab}
                label={month ? tr("Resumen del mes", "Month summary") : tr("Resumen de la semana", "Week summary")}
              >
                {tab === "once" && (
                  <Section
                    title={tabs[0].label}
                    intro={tr(
                      "En 4-3-3, los que más superaron lo que esperaba el modelo en cada línea. Porteros y defensas suman también los goles que recibió su equipo frente a lo esperado.",
                      "In a 4-3-3, those who beat the model's expectations the most in each line. Goalkeepers and defenders also count the goals their team conceded against expectations.",
                    )}
                  >
                    <OnceSemana eleven={data.eleven} />
                  </Section>
                )}
                {tab === "equipos" && (
                  <Section
                    title={tr("Equipos", "Teams")}
                    intro={tr(
                      "Resultado, goles y córners de cada equipo frente a la casa: el 1X2 sin margen y la línea principal antes del partido (si no hay, lo que esperaba el modelo).",
                      "Each team's result, goals and corners against the bookmaker: the margin-free 1X2 and the main line before kick-off (if there is none, what the model expected).",
                    )}
                  >
                    <Ranking rows={data.teams} kind="equipos" />
                  </Section>
                )}
                {tab === "jugadores" && (
                  <Section
                    title={tr("Jugadores", "Players")}
                    intro={tr(
                      "Remates, remates a puerta, goles y asistencias frente a lo que esperaba el modelo antes del partido, ajustado a los minutos que jugó (desde 30).",
                      "Shots, shots on target, goals and assists against what the model expected before kick-off, adjusted to the minutes played (from 30).",
                    )}
                  >
                    <Ranking rows={data.players} kind="jugadores" />
                  </Section>
                )}
              </Tabs>
              <p className="pb-10 text-nota text-grafito">
                {tr(
                  "Cada dato suma de −1 a +1: 0 es lo esperado y cuanto más raro fue por arriba, más cerca de +1.",
                  "Each item adds from −1 to +1: 0 is as expected and the more unusual on the upside, the closer to +1.",
                )}{" "}
                {month
                  ? tr("El mes es la suma de sus partidos.", "The month is the sum of its matches.")
                  : tr("La semana es la suma de sus partidos.", "The week is the sum of its matches.")}
              </p>
            </>
          )}
        </>
  );
}

function Coverage({ data }: { data: WeekRecap }) {
  const c = data.coverage;
  const since = data.history_since ? shortDate(data.history_since) : null;
  const parts = [
    tr(
      `${c.played} ${c.played === 1 ? "partido jugado" : "partidos jugados"}${c.scheduled ? ` y ${c.scheduled} por jugarse` : ""}`,
      `${c.played} ${c.played === 1 ? "match played" : "matches played"}${c.scheduled ? ` and ${c.scheduled} still to play` : ""}`,
    ),
    tr(`equipos medidos frente a la casa en ${c.team_matches}`, `teams measured against the bookmaker in ${c.team_matches}`),
    tr(
      `jugadores, en los ${c.with_prediction} con la previa del modelo guardada${since ? ` (se guarda desde el ${since})` : ""}`,
      `players, in the ${c.with_prediction} with the model's preview saved${since ? ` (saved since ${since})` : ""}`,
    ),
  ];
  return <p className="mb-6 text-nota text-grafito">{`${parts.join("; ")}.`}</p>;
}

function Destacado({ kind, month, row }: { kind: "equipo" | "jugador"; month: boolean; row: WeekTeam | WeekPlayer | null }) {
  const title =
    kind === "equipo"
      ? month
        ? tr("Equipo del mes", "Team of the month")
        : tr("Equipo de la semana", "Team of the week")
      : month
        ? tr("Jugador del mes", "Player of the month")
        : tr("Jugador de la semana", "Player of the week");
  const player = row && "player_id" in row ? row : null;
  return (
    <section aria-label={title} className="border-t-[3px] border-tinta pt-3">
      <h2 className="cond text-lateral leading-none font-black uppercase">{title}</h2>
      {!row ? (
        <p className="mt-2 text-nota text-grafito">
          {kind === "equipo"
            ? tr("Aún no hay equipos con partidos jugados y su vara de la casa.", "No teams yet with matches played and the bookmaker's yardstick.")
            : tr(
                "Aún no hay jugadores: hacen falta partidos jugados con la previa del modelo guardada.",
                "No players yet: it needs matches played with the model's preview saved.",
              )}
        </p>
      ) : (
        <>
          <div className="mt-3 flex items-center gap-3">
            <Crest id={player ? player.team_id : (row as WeekTeam).team_id} size={40} />
            <div className="min-w-0">
              <p className="semi truncate text-xl font-bold">{row.name}</p>
              <p className="truncate text-nota text-grafito">
                {player
                  ? [player.team, positionName(player.position), `${player.minutes} min`]
                      .filter(Boolean)
                      .join(" · ")
                  : competitionName((row as WeekTeam).competition)}
              </p>
            </div>
          </div>
          <div className="mt-4 flex gap-8">
            <Figure
              size="lg"
              value={signedNum(row.score)}
              label={tr("de sorpresa", "surprise")}
              tone={row.score > 0 ? "boli" : row.score < 0 ? "rojo" : undefined}
            />
            <Figure value={row.n_matches} label={row.n_matches === 1 ? tr("partido", "match") : tr("partidos", "matches")} />
          </div>
          <MatchItems matches={row.matches} />
        </>
      )}
    </section>
  );
}
