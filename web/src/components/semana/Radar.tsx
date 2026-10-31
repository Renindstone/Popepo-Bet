"use client";

import { useState } from "react";
import { Crest } from "@/components/Crest";
import { NotaClaude } from "@/components/NotaClaude";
import { Empty, ErrorNote, Loading, Section, Tag } from "@/components/ui";
import { type ApiError, post, useApi } from "@/lib/api";
import { pct, signedNum } from "@/lib/format";
import { tr } from "@/lib/i18n";
import { useMe } from "@/lib/me";
import type { AiNote, NextMatch, RadarPlayer, RadarReport, RadarTeam } from "@/lib/types";

/** «Milan en baja» / «Genoa en racha»: siempre con palabra, nunca solo color */
export function AlertTag({ alert }: { alert: { name: string; kind: "racha" | "baja" } }) {
  return (
    <Tag tone={alert.kind === "racha" ? "boli" : "rojo"}>
      {alert.kind === "racha" ? tr(`${alert.name} en racha`, `${alert.name} on a run`) : tr(`${alert.name} en baja`, `${alert.name} in a slump`)}
    </Tag>
  );
}

/** Por qué está en el radar: el batacazo o el pinchazo más llamativo, o la suma de las 4 semanas */
export function reasonText(r: Pick<RadarTeam, "reason" | "score" | "n_matches">): string {
  const { type, label, date, p_win } = r.reason;
  const day = date ? `${date.slice(8, 10)}/${date.slice(5, 7)}` : "";
  const when = day ? tr(` el ${day}`, ` on ${day}`) : "";
  const odds = p_win != null ? tr(`, con un ${pct(p_win)} de ganar según la casa`, `, with a ${pct(p_win)} chance to win according to the bookmaker`) : "";
  if (type === "batacazo") return tr(`Batacazo: ${label}${when}${odds}.`, `Big upset: ${label}${when}${odds}.`);
  if (type === "pinchazo") return tr(`Pinchazo: ${label}${when}${odds}.`, `Slip-up: ${label}${when}${odds}.`);
  const n = r.n_matches === 1 ? tr("partido", "match") : tr("partidos", "matches");
  return tr(
    `Suma ${signedNum(r.score)} en ${r.n_matches} ${n}; el más llamativo, ${label}${when}${odds}.`,
    `Adds up to ${signedNum(r.score)} in ${r.n_matches} ${n}; the most striking, ${label}${when}${odds}.`,
  );
}

function nextText(matches: NextMatch[]): string {
  if (!matches.length) return tr("Sin partido en las próximas dos semanas.", "No match in the next two weeks.");
  const list = matches.map((m) => `${m.label}, ${m.kickoff_local}`);
  return tr(`Próximo: ${list.join("; después, ")}.`, `Next: ${list.join("; then, ")}.`);
}

function Investigar({ kind, id, note, onDone }: { kind: "team" | "player"; id: number; note?: AiNote | null; onDone: () => void }) {
  const { me } = useMe();
  const [state, setState] = useState<{ busy: boolean; error?: ApiError }>({ busy: false });
  if (note && note.status !== "error") return <NotaClaude note={note} />;
  if (!me?.can_investigate) return note ? <NotaClaude note={note} /> : null;
  async function go() {
    setState({ busy: true });
    try {
      await post("/radar/investigate", { kind, id });
      onDone();
      setState({ busy: false });
    } catch (e) {
      setState({ busy: false, error: e as ApiError });
    }
  }
  return (
    <>
      {note && <NotaClaude note={note} />}
      <button
        type="button"
        onClick={go}
        disabled={state.busy}
        className="mt-1 inline-flex min-h-10 items-center text-nota font-bold text-boli underline underline-offset-4 disabled:opacity-50"
      >
        {state.busy
          ? tr("Pidiéndoselo a Claude…", "Asking Claude…")
          : note
            ? tr("Volver a intentarlo", "Try again")
            : tr("Investigar con Claude", "Look into it with Claude")}
      </button>
      {state.error && <ErrorNote error={state.error} />}
    </>
  );
}

// En el celular cada lista enseña las 3 primeras: el radar entero medía unos 4.000 px
const MOBILE_ROWS = 3;

function cutClass(i: number, all: boolean): string {
  return !all && i >= MOBILE_ROWS ? "hidden lg:block" : "";
}

function ShowAll({ total, all, onToggle }: { total: number; all: boolean; onToggle: () => void }) {
  if (total <= MOBILE_ROWS) return null;
  return (
    <button
      type="button"
      onClick={onToggle}
      className="mt-1 inline-flex min-h-10 items-center text-interfaz font-bold text-boli underline underline-offset-4 lg:hidden"
    >
      {all ? tr("Mostrar menos", "Show fewer") : tr(`Mostrar los ${total}`, `Show all ${total}`)}
    </button>
  );
}

function TeamRow({ row, onDone, className = "" }: { row: RadarTeam; onDone: () => void; className?: string }) {
  return (
    <li className={`py-3 ${className}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="semi text-lg leading-tight font-bold">
            <Crest id={row.team_id} size={20} className="mr-1.5 -mt-0.5" />
            {row.name}{" "}
            {row.reason.type !== "suma" && (
              <Tag tone={row.kind === "racha" ? "boli" : "rojo"} className="ml-1 align-middle">
                {row.reason.type === "batacazo" ? tr("Batacazo", "Big upset") : tr("Pinchazo", "Slip-up")}
              </Tag>
            )}
          </p>
          <p className="mt-0.5 text-nota text-grafito">{reasonText(row)}</p>
          {row.figures.length > 0 && (
            <p className="text-nota">
              {tr("Figuras:", "Key players:")} {row.figures.map((f) => `${f.name} (${signedNum(f.score, 1)})`).join(", ")}
            </p>
          )}
          <p className="text-nota text-grafito">{nextText(row.next_matches)}</p>
        </div>
        <span className={`cond num shrink-0 text-lateral leading-none font-extrabold ${row.kind === "racha" ? "text-boli" : "text-rojo"}`}>
          {signedNum(row.score)}
        </span>
      </div>
      <Investigar kind="team" id={row.team_id} note={row.note} onDone={onDone} />
    </li>
  );
}

function PlayerRow({ row, onDone, className = "" }: { row: RadarPlayer; onDone: () => void; className?: string }) {
  return (
    <li className={`py-3 ${className}`}>
      <div className="flex items-start justify-between gap-4">
        <div className="min-w-0">
          <p className="semi text-lg leading-tight font-bold">
            <Crest id={row.team_id} size={20} className="mr-1.5 -mt-0.5" />
            {row.name} <span className="text-nota font-normal text-grafito">{row.team}</span>
          </p>
          <p className="mt-0.5 text-nota text-grafito">
            {tr(
              `${row.n_matches} ${row.n_matches === 1 ? "partido" : "partidos"}, ${row.minutes} min; el mejor, ${row.best.label}.`,
              `${row.n_matches} ${row.n_matches === 1 ? "match" : "matches"}, ${row.minutes} min; the best, ${row.best.label}.`,
            )}
          </p>
          <p className="text-nota text-grafito">{nextText(row.next_matches)}</p>
        </div>
        <span className="cond num shrink-0 text-lateral leading-none font-extrabold text-boli">{signedNum(row.score)}</span>
      </div>
      <Investigar kind="player" id={row.player_id} note={row.note} onDone={onDone} />
    </li>
  );
}

function hasPending(r?: RadarReport): boolean {
  return !!r && [...r.racha, ...r.baja, ...r.jugadores].some((x) => x.note?.status === "pendiente" || x.note?.status === "trabajando");
}

/** «En el radar»: los que más se salieron de lo esperado en las últimas 4 semanas, para seguirlos */
export function Radar() {
  const { data, error, mutate } = useApi<RadarReport>("/radar", {
    refreshInterval: (latest) => (hasPending(latest) ? 15000 : 0),
  });
  const refresh = () => void mutate();
  const [all, setAll] = useState<Record<string, boolean>>({});
  const toggle = (key: string) => setAll({ ...all, [key]: !all[key] });
  const list = (key: string, title: string, rows: RadarTeam[], empty: string) => (
    <div>
      <h3 className="cond border-b border-tinta pb-1 text-destacado leading-none font-black uppercase">{title}</h3>
      {rows.length === 0 ? (
        <Empty>{empty}</Empty>
      ) : (
        <>
          <ul className="divide-y divide-regla-suave">
            {rows.map((r, i) => (
              <TeamRow key={r.team_id} row={r} onDone={refresh} className={cutClass(i, !!all[key])} />
            ))}
          </ul>
          <ShowAll total={rows.length} all={!!all[key]} onToggle={() => toggle(key)} />
        </>
      )}
    </div>
  );
  return (
    <Section
      title={tr("En el radar", "On the radar")}
      intro={tr(
        "Los equipos y jugadores que más se salieron de lo esperado en las últimas 4 semanas, con su próximo partido, para seguirlos de cerca. Un batacazo es ganar cuando la casa daba un 25 % o menos; un pinchazo, perder cuando daba un 60 % o más. Es un aviso, no una señal: con el historial desde 2023, quien dio la sorpresa no la repite más de lo que espera la casa.",
        "The teams and players who strayed furthest from expectations over the last 4 weeks, with their next match, to keep an eye on them. A big upset is winning when the bookmaker gave 25 % or less; a slip-up, losing when it gave 60 % or more. It is a warning, not a signal: with the history since 2023, whoever pulled off the surprise does not repeat it more than the bookmaker expects.",
      )}
    >
      {error ? (
        <ErrorNote error={error} onRetry={refresh} />
      ) : !data ? (
        <Loading lines={4} label={tr("Calculando el radar", "Working out the radar")} />
      ) : (
        <div className="space-y-8">
          <div className="grid gap-x-10 gap-y-8 lg:grid-cols-2">
            {list("racha", tr("En racha", "On a run"), data.racha, tr("Ningún equipo en racha en las últimas 4 semanas.", "No team on a run in the last 4 weeks."))}
            {list("baja", tr("En baja", "In a slump"), data.baja, tr("Ningún equipo en baja en las últimas 4 semanas.", "No team in a slump in the last 4 weeks."))}
          </div>
          <div>
            <h3 className="cond border-b border-tinta pb-1 text-destacado leading-none font-black uppercase">
              {tr("Jugadores en racha", "Players on a run")}
            </h3>
            {data.jugadores.length === 0 ? (
              <Empty>
                {tr(
                  "Aún no hay jugadores en racha: hacen falta partidos con la previa del modelo guardada.",
                  "No players on a run yet: it needs matches with the model's preview saved.",
                )}
              </Empty>
            ) : (
              <>
                <ul className="grid gap-x-10 divide-y divide-regla-suave lg:grid-cols-2 lg:divide-y-0">
                  {data.jugadores.map((p, i) => (
                    <PlayerRow key={p.player_id} row={p} onDone={refresh} className={cutClass(i, !!all.jugadores)} />
                  ))}
                </ul>
                <ShowAll total={data.jugadores.length} all={!!all.jugadores} onToggle={() => toggle("jugadores")} />
              </>
            )}
          </div>
        </div>
      )}
    </Section>
  );
}
