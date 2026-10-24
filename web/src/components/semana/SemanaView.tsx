"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Crest } from "@/components/Crest";
import { MatchItems, POSITIONS, Ranking } from "@/components/semana/Ranking";
import { OnceSemana } from "@/components/semana/OnceSemana";
import { Tabs, useHashTab } from "@/components/Tabs";
import { Empty, ErrorNote, Figure, Loading, PageTitle, Section } from "@/components/ui";
import { useApi } from "@/lib/api";
import { competitionName, shiftDay, shortDate, signedNum, weekLabel, weekStart } from "@/lib/format";
import { useToday } from "@/lib/hooks";
import type { WeekPlayer, WeekRecap, WeekTeam } from "@/lib/types";

const TABS = [
  { id: "once", label: "Once de la semana" },
  { id: "equipos", label: "Equipos" },
  { id: "jugadores", label: "Jugadores" },
] as const;

const navLink =
  "inline-flex h-10 items-center rounded-[3px] border border-regla bg-hoja px-3 text-interfaz font-semibold hover:border-grafito";

/** Resumen de la semana: quién superó lo que esperaban la casa (equipos) y el modelo (jugadores) */
export function SemanaView() {
  const params = useSearchParams();
  const today = useToday();
  const current = today ? weekStart(today) : "";
  const asked = params.get("semana");
  const monday = asked ? weekStart(asked) : current;
  const { data, error, mutate } = useApi<WeekRecap>(monday ? `/week?day=${monday}` : null);

  const tabs = TABS.map((t) => ({
    ...t,
    count: t.id === "equipos" ? data?.teams.length : t.id === "jugadores" ? data?.players.length : undefined,
  }));
  const [tab, setTab] = useHashTab(tabs);
  const keep = tab !== tabs[0].id ? `#${tab}` : "";

  const nav = monday && (
    <>
      <Link href={`/semana?semana=${shiftDay(monday, -7)}${keep}`} className={navLink}>
        Semana anterior
      </Link>
      {monday < current && (
        <Link href={`/semana?semana=${shiftDay(monday, 7)}${keep}`} className={navLink}>
          Semana siguiente
        </Link>
      )}
      {monday !== current && (
        <Link href={`/semana${keep}`} className="inline-flex h-10 items-center px-2 text-interfaz font-semibold text-boli underline underline-offset-4">
          Volver a esta semana
        </Link>
      )}
    </>
  );
  const label = monday ? weekLabel(monday) : "";

  return (
    <>
      <PageTitle
        title="Semana"
        sub={monday ? `${label.charAt(0).toUpperCase()}${label.slice(1)}${data?.status === "en_curso" ? ", en curso" : ""}.` : null}
        actions={nav}
      />
      {error ? (
        <div className="pb-10">
          <ErrorNote error={error} onRetry={() => mutate()} />
        </div>
      ) : !data ? (
        <div className="pb-10">
          <Loading lines={6} label="Calculando el resumen de la semana" />
        </div>
      ) : (
        <>
          <p className="mb-3 max-w-[72ch] border-l-[3px] border-tarjeta bg-tarjeta-suave px-3 py-2 text-interfaz">{data.note}</p>
          <Coverage data={data} />
          {data.coverage.played === 0 ? (
            <div className="pb-10">
              <Empty>Esta semana aún no se jugó ningún partido de las seis competiciones.</Empty>
            </div>
          ) : (
            <>
              <div className="grid gap-6 pb-8 lg:grid-cols-2">
                <Destacado kind="equipo" row={data.team_of_week} />
                <Destacado kind="jugador" row={data.player_of_week} />
              </div>
              <Tabs tabs={tabs} current={tab} onSelect={setTab} label="Resumen de la semana">
                {tab === "once" && (
                  <Section
                    title="Once de la semana"
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
                Cada dato suma de −1 a +1: 0 es lo esperado y cuanto más raro fue por arriba, más cerca de +1. La semana
                es la suma de sus partidos.
              </p>
            </>
          )}
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

function Destacado({ kind, row }: { kind: "equipo" | "jugador"; row: WeekTeam | WeekPlayer | null }) {
  const title = kind === "equipo" ? "Equipo de la semana" : "Jugador de la semana";
  const player = row && "player_id" in row ? row : null;
  return (
    <section aria-label={title} className="rounded-[4px] border border-regla bg-hoja p-5">
      <h2 className="semi text-base font-bold">{title}</h2>
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
