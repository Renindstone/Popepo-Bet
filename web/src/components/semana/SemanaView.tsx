"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Crest } from "@/components/Crest";
import { MatchItems, POSITIONS, Ranking } from "@/components/semana/Ranking";
import { OnceSemana } from "@/components/semana/OnceSemana";
import { Radar } from "@/components/semana/Radar";
import { Tabs, useHashTab } from "@/components/Tabs";
import { Empty, ErrorNote, Figure, Loading, PageTitle, Section } from "@/components/ui";
import { useApi } from "@/lib/api";
import { competitionName, monthAvailableFrom, rangeLabel, shiftDay, shortDate, signedNum, weekStart } from "@/lib/format";
import { useToday } from "@/lib/hooks";
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
  const per = month ? "del mes" : "de la semana";

  const tabs = [
    { id: "once", label: `Once ${per}` },
    { id: "equipos", label: "Equipos", count: recap?.teams.length },
    { id: "jugadores", label: "Jugadores", count: recap?.players.length },
  ];
  const [tab, setTab] = useHashTab(tabs);
  const keep = tab !== tabs[0].id ? `#${tab}` : "";
  const href = (week: string | null) =>
    `/sorpresas?${[month ? "periodo=mes" : null, week ? `semana=${week}` : null].filter(Boolean).join("&")}${keep}`;
  const newest = month ? lastFull : current;

  const nav = last && (
    <>
      <Link href={href(shiftDay(last, -step))} className={navLink}>
        {month ? "Mes anterior" : "Semana anterior"}
      </Link>
      {last < newest && (
        <Link href={href(shiftDay(last, step))} className={navLink}>
          {month ? "Mes siguiente" : "Semana siguiente"}
        </Link>
      )}
      {last !== newest && (
        <Link href={href(null)} className="inline-flex h-10 items-center px-2 text-interfaz font-bold text-boli underline underline-offset-4">
          {month ? "Volver al último mes" : "Volver a esta semana"}
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
        title="Sorpresas"
        sub={label ? `${label.charAt(0).toUpperCase()}${label.slice(1)}${recap?.status === "en_curso" ? ", en curso" : ""}.` : null}
        actions={nav}
      />
      <div role="group" aria-label="Periodo" className="-mt-2 mb-6 flex flex-wrap items-center gap-2">
        {month ? (
          <Link href="/sorpresas" className={pickerOff}>
            Semana
          </Link>
        ) : (
          <span aria-current="page" className={pickerOn}>
            Semana
          </span>
        )}
        {month ? (
          <span aria-current="page" className={pickerOn}>
            Mes
          </span>
        ) : monthLocked ? (
          <span className="inline-flex h-10 items-center border border-regla px-4 text-interfaz font-bold text-grafito">
            {monthFrom ? `Mes · desde el ${shortDate(monthFrom)}` : "Mes · cuando haya 4 semanas"}
          </span>
        ) : (
          <Link href="/sorpresas?periodo=mes" className={pickerOff}>
            Mes
          </Link>
        )}
        <span className="text-nota text-grafito">El mes son las 4 semanas completas que terminan en la elegida.</span>
      </div>
      {error ? (
        <div className="pb-10">
          <ErrorNote error={error} onRetry={() => mutate()} />
        </div>
      ) : !data ? (
        <div className="pb-10">
          <Loading lines={6} label="Calculando las sorpresas" />
        </div>
      ) : !data.available ? (
        <>
          <p className="mb-8 max-w-[72ch] border-t-[3px] border-tarjeta bg-tarjeta-suave px-3 py-2 text-interfaz">
            {data.available_from
              ? `El mes llega el ${shortDate(data.available_from)}: hacen falta 4 semanas completas con la previa del modelo guardada.`
              : "El mes llegará cuando haya 4 semanas completas con la previa del modelo guardada."}
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
  const per = month ? "del mes" : "de la semana";
  return (
        <>
          <p className="mb-3 max-w-[72ch] border-t-[3px] border-tarjeta bg-tarjeta-suave px-3 py-2 text-interfaz">{data.note}</p>
          <Coverage data={data} />
          {data.coverage.played === 0 ? (
            <>
              <div className="pb-8">
                <Empty>{`${month ? "En este mes" : "Esta semana"} aún no se jugó ningún partido de las seis competiciones.`}</Empty>
              </div>
              {/* El radar mira los últimos 28 días: no depende de que la semana elegida tenga partidos */}
              <Radar />
            </>
          ) : (
            <>
              <div className="grid gap-x-10 gap-y-8 pb-8 lg:grid-cols-2">
                <Destacado kind="equipo" per={per} row={data.team_of_week} />
                <Destacado kind="jugador" per={per} row={data.player_of_week} />
              </div>
              <Radar />
              <Tabs tabs={tabs} current={tab} onSelect={setTab} label={`Resumen ${per}`}>
                {tab === "once" && (
                  <Section
                    title={`Once ${per}`}
                    intro="En 4-3-3, los que más superaron lo que esperaba el modelo en cada línea. Porteros y defensas suman también los goles que recibió su equipo frente a lo esperado."
                  >
                    <OnceSemana eleven={data.eleven} />
                  </Section>
                )}
                {tab === "equipos" && (
                  <Section
                    title="Equipos"
                    intro="Resultado, goles y córners de cada equipo frente a la casa: el 1X2 sin margen y la línea principal antes del partido (si no hay, lo que esperaba el modelo)."
                  >
                    <Ranking rows={data.teams} kind="equipos" />
                  </Section>
                )}
                {tab === "jugadores" && (
                  <Section
                    title="Jugadores"
                    intro={`Remates, remates a puerta, goles y asistencias frente a lo que esperaba el modelo antes del partido, ajustado a los minutos que jugó (desde 30).`}
                  >
                    <Ranking rows={data.players} kind="jugadores" />
                  </Section>
                )}
              </Tabs>
              <p className="pb-10 text-nota text-grafito">
                Cada dato suma de −1 a +1: 0 es lo esperado y cuanto más raro fue por arriba, más cerca de +1.{" "}
                {month ? "El mes" : "La semana"} es la suma de sus partidos.
              </p>
            </>
          )}
        </>
  );
}

function Coverage({ data }: { data: WeekRecap }) {
  const c = data.coverage;
  const parts = [
    `${c.played} ${c.played === 1 ? "partido jugado" : "partidos jugados"}${c.scheduled ? ` y ${c.scheduled} por jugarse` : ""}`,
    `equipos medidos frente a la casa en ${c.team_matches}`,
    `jugadores, en los ${c.with_prediction} con la previa del modelo guardada${data.history_since ? ` (se guarda desde el ${shortDate(data.history_since)})` : ""}`,
  ];
  return <p className="mb-6 text-nota text-grafito">{`${parts.join("; ")}.`}</p>;
}

function Destacado({ kind, per, row }: { kind: "equipo" | "jugador"; per: string; row: WeekTeam | WeekPlayer | null }) {
  const title = `${kind === "equipo" ? "Equipo" : "Jugador"} ${per}`;
  const player = row && "player_id" in row ? row : null;
  return (
    <section aria-label={title} className="border-t-[3px] border-tinta pt-3">
      <h2 className="cond text-lateral leading-none font-black uppercase">{title}</h2>
      {!row ? (
        <p className="mt-2 text-nota text-grafito">
          {kind === "equipo"
            ? "Aún no hay equipos con partidos jugados y su vara de la casa."
            : "Aún no hay jugadores: hacen falta partidos jugados con la previa del modelo guardada."}
        </p>
      ) : (
        <>
          <div className="mt-3 flex items-center gap-3">
            <Crest id={player ? player.team_id : (row as WeekTeam).team_id} size={40} />
            <div className="min-w-0">
              <p className="semi truncate text-xl font-bold">{row.name}</p>
              <p className="truncate text-nota text-grafito">
                {player
                  ? [player.team, player.position ? POSITIONS[player.position] : null, `${player.minutes} min`]
                      .filter(Boolean)
                      .join(" · ")
                  : competitionName((row as WeekTeam).competition)}
              </p>
            </div>
          </div>
          <div className="mt-4 flex gap-8">
            <Figure size="lg" value={signedNum(row.score)} label="de sorpresa" tone={row.score > 0 ? "boli" : row.score < 0 ? "rojo" : undefined} />
            <Figure value={row.n_matches} label={row.n_matches === 1 ? "partido" : "partidos"} />
          </div>
          <MatchItems matches={row.matches} />
        </>
      )}
    </section>
  );
}
