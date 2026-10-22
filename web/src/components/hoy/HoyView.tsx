"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { useCallback, useState } from "react";
import { CaptureDrop } from "@/components/capturas/CaptureDrop";
import { Crest } from "@/components/Crest";
import { PenMark } from "@/components/PenMark";
import { PickRecord } from "@/components/PickRecord";
import { Tabs, useHashTab } from "@/components/Tabs";
import { Button, EdgeBar, Empty, ErrorNote, Figure, Loading, PageTitle, Section, Tag, TriBar } from "@/components/ui";
import { api, type ApiError, useApi } from "@/lib/api";
import {
  competitionName,
  longDay,
  money,
  odds,
  pct,
  resultText,
  shiftDay,
  signedPct,
  splitMatch,
  stageText,
} from "@/lib/format";
import { useToday } from "@/lib/hooks";
import { betLabel, bookmakerName } from "@/lib/markets";
import type { Capture, DayMatch, PastValueBet, Performance, PickOfDay, PicksReport, PropMinOdds, ValueBet } from "@/lib/types";

function dayTitle(day: string, today: string): string {
  if (day === today) return "Hoy";
  if (day === shiftDay(today, 1)) return "Mañana";
  if (day === shiftDay(today, -1)) return "Ayer";
  const d = longDay(day);
  return d.charAt(0).toUpperCase() + d.slice(1);
}

// Las tres listas una debajo de otra medían 7.800 px en el celular un sábado de 14 partidos: van en pestañas
const TABS = [
  { id: "partidos", label: "Partidos" },
  { id: "valor", label: "Con valor" },
  { id: "props", label: "Props" },
] as const;

export function HoyView() {
  const params = useSearchParams();
  const today = useToday();
  const day = params.get("dia") ?? today;
  const { data, error, isLoading, mutate } = useApi<PicksReport>(day ? `/picks?day=${day}` : null);
  const { data: perf } = useApi<Performance>("/performance");
  const [recalc, setRecalc] = useState<{ busy: boolean; error?: ApiError }>({ busy: false });
  const past = !!day && !!today && day < today;

  // Los días pasados solo guardan las apuestas con valor: sin partidos ni props no hacen falta pestañas
  const matches = !past ? data?.matches : undefined;
  const props = !past ? data?.props_to_check : undefined;
  const counts: Record<string, number | undefined> = {
    partidos: matches?.length,
    valor: data?.value_bets.length,
    props: props?.length,
  };
  const tabs = TABS.filter((t) => t.id === "valor" || counts[t.id] != null).map((t) => ({ ...t, count: counts[t.id] }));
  const [tab, setTab] = useHashTab(tabs);
  // Al cambiar de día se queda en la misma pestaña
  const keep = data && tab !== tabs[0].id ? `#${tab}` : "";

  async function recalculate() {
    setRecalc({ busy: true });
    try {
      const fresh = await api<PicksReport>(`/picks?day=${day}&refresh=true`);
      await mutate(fresh, { revalidate: false });
      setRecalc({ busy: false });
    } catch (e) {
      setRecalc({ busy: false, error: e as ApiError });
    }
  }

  const nav = day && (
    <>
      <Link
        href={`/?dia=${shiftDay(day, -1)}${keep}`}
        className="inline-flex h-10 items-center rounded-[3px] border border-regla bg-hoja px-3 text-interfaz font-semibold hover:border-grafito"
      >
        Día anterior
      </Link>
      <Link
        href={`/?dia=${shiftDay(day, 1)}${keep}`}
        className="inline-flex h-10 items-center rounded-[3px] border border-regla bg-hoja px-3 text-interfaz font-semibold hover:border-grafito"
      >
        Día siguiente
      </Link>
      {day !== today && (
        <Link href={`/${keep}`} className="inline-flex h-10 items-center px-2 text-interfaz font-semibold text-boli underline underline-offset-4">
          Volver a hoy
        </Link>
      )}
      {!past && (
        <Button onClick={recalculate} disabled={recalc.busy || isLoading}>
          {recalc.busy ? "Recalculando…" : "Recalcular"}
        </Button>
      )}
    </>
  );

  return (
    <>
      <PageTitle
        title={day && today ? dayTitle(day, today) : "Hoy"}
        sub={day ? `${longDay(day)}${past ? ". Lo que se guardó ese día." : ""}` : null}
        actions={nav}
      />
      {recalc.error && (
        <div className="mb-6">
          <ErrorNote error={recalc.error} />
        </div>
      )}

      <div className="grid gap-x-10 gap-y-6 pb-10 lg:grid-cols-[minmax(0,1fr)_300px]">
        <div>
          {error ? (
            <ErrorNote error={error} onRetry={() => mutate()} />
          ) : !data ? (
            <div className="rounded-[4px] border border-regla bg-hoja p-6">
              <Loading lines={4} label="Calculando las apuestas del día" />
            </div>
          ) : data.pick_of_day ? (
            <Slip pick={data.pick_of_day} past={past} bankroll={perf?.bankroll.bankroll} currency={perf?.bankroll.currency} />
          ) : (
            <NoPick note={data.notes?.find((n) => n.startsWith("Hoy no hay")) ?? null} past={past} />
          )}
          {data?.matches && <DayCount report={data} />}
          {data?.notes
            ?.filter((n) => !n.startsWith("Hoy no hay"))
            .map((n) => (
              <p key={n} className="mt-3 border-l-[3px] border-tarjeta bg-tarjeta-suave px-3 py-2 text-interfaz">
                {n}
              </p>
            ))}
        </div>
        <div className="space-y-6">
          <PickRecord />
          {!past && <CaptureQuick />}
          <MarginNote />
        </div>
      </div>

      {data &&
        (tabs.length > 1 ? (
          <Tabs tabs={tabs} current={tab} onSelect={setTab} label="Listas del día">
            {tab === "partidos" && matches && (
              <Section title="Partidos del día">
                <DayMatches rows={matches} />
              </Section>
            )}
            {tab === "valor" && <ValueSection rows={data.value_bets} past={past} />}
            {tab === "props" && props && (
              <Section
                title="Props con cuota mínima"
                intro="Mercados para los que no tenemos cuota. Si tu casa paga al menos la cuota mínima, el modelo ve un 5 % de valor. Sin un mercado afilado como referencia, el margen de error es mayor."
              >
                <Props rows={props} />
              </Section>
            )}
          </Tabs>
        ) : (
          <ValueSection rows={data.value_bets} past={past} />
        ))}
    </>
  );
}

function ValueSection({ rows, past }: { rows: (ValueBet | PastValueBet)[]; past: boolean }) {
  return (
    <Section
      title="Otras apuestas con valor"
      intro={
        past
          ? "Las que el sistema guardó ese día con valor positivo."
          : "Cuotas de bet365 y Betano donde nuestra estimación supera lo que implica la cuota. Solo las que pasan el corte de valor, probabilidad y confianza pueden ser apuesta del día."
      }
    >
      <ValueBets rows={rows} />
    </Section>
  );
}

// --------------------------------------------------------------------------- capturas

/** Atajo para revisar una cuota vista en la casa de apuestas: se sube y se abre en Capturas */
function CaptureQuick() {
  const router = useRouter();
  const onUploaded = useCallback((c: Capture) => router.push(`/capturas?nueva=${c.id}`), [router]);
  return (
    <div>
      <h2 className="semi mb-1 text-base font-bold text-tinta">¿Viste una cuota?</h2>
      <p className="mb-3 text-nota text-grafito">
        Sube o pega la captura de Betano o bet365: una IA la lee y el modelo te dice si tiene valor.
      </p>
      <CaptureDrop onUploaded={onUploaded} compact />
    </div>
  );
}

// --------------------------------------------------------------------------- apuesta del día

function Slip({ pick, past, bankroll, currency }: { pick: PickOfDay; past: boolean; bankroll?: number; currency?: string }) {
  const [home, away] = splitMatch(pick.match);
  const label = betLabel(pick.market, pick.selection, pick.line, { home, away });
  const reasons = (pick.reasons ?? []).filter((r) => !r.startsWith("pick_id="));
  const evaluarHref = pick.match_id
    ? `/evaluar?partido=${pick.match_id}&mercado=${pick.market}&seleccion=${pick.selection}${pick.line != null ? `&linea=${pick.line}` : ""}`
    : null;

  return (
    <article aria-labelledby="apuesta-del-dia" className="relative rounded-[4px] border border-regla bg-hoja">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-5 pt-4 sm:px-6">
        <h2 id="apuesta-del-dia" className="semi text-interfaz font-bold text-boli">
          Apuesta del día
        </h2>
        <p className="text-nota text-grafito">
          {pick.competition && <span>{pick.competition}</span>}
          {pick.kickoff_local && <span className="num">, {pick.kickoff_local.slice(11)}</span>}
        </p>
      </div>
      <p className="cond px-5 pt-1 pb-4 text-[1.9rem] leading-tight font-bold sm:px-6 sm:text-[2.2rem]">
        {pick.match_id ? (
          <Link href={`/partidos/${pick.match_id}`} className="hover:underline hover:decoration-regla hover:underline-offset-4">
            <Crest id={pick.home_id} size={30} className="mr-2 -mt-1" />
            {home} <span className="font-medium text-grafito">vs</span>{" "}
            <Crest id={pick.away_id} size={30} className="mr-2 -mt-1" />
            {away}
          </Link>
        ) : (
          pick.match
        )}
      </p>

      {/* Línea de corte del boleto */}
      <div className="relative">
        <div className="mx-5 border-t-2 border-dashed border-regla sm:mx-6" />
        <span className="absolute top-1/2 -left-[9px] size-4 -translate-y-1/2 rounded-full border-r border-regla bg-papel" />
        <span className="absolute top-1/2 -right-[9px] size-4 -translate-y-1/2 rounded-full border-l border-regla bg-papel" />
      </div>

      <div className="grid gap-x-8 gap-y-5 px-5 pt-5 pb-5 sm:grid-cols-[1fr_auto] sm:px-6">
        <div className="min-w-0">
          <p className="text-[1.35rem] leading-snug font-semibold">{label}</p>
          <p className="mt-0.5 text-grafito">
            {pick.bookmaker ? `en ${bookmakerName(pick.bookmaker)}` : null}
            {pick.stage ? `${pick.bookmaker ? ". " : ""}${stageText(pick.stage)}` : null}
          </p>
        </div>
        <div className="relative justify-self-start px-4 py-2 sm:justify-self-end">
          <PenMark kind="circle" className="-inset-x-3 -inset-y-2 h-[calc(100%+1rem)] w-[calc(100%+1.5rem)]" />
          <p className="cond num text-[3.4rem] leading-none font-extrabold">{odds(pick.odds)}</p>
          <p className="text-center text-nota text-grafito">cuota</p>
        </div>
      </div>

      {pick.prob != null && (
        <div className="px-5 pb-5 sm:px-6">
          <EdgeBar prob={pick.prob} odds={pick.odds} />
        </div>
      )}

      <div className="grid grid-cols-2 gap-x-6 gap-y-4 border-t border-regla-suave px-5 py-4 sm:grid-cols-4 sm:px-6">
        <Figure value={signedPct(pick.ev)} label="valor esperado" tone={pick.ev > 0 ? "boli" : "rojo"} />
        {pick.confidence != null && <Figure value={pct(pick.confidence)} label="confianza" />}
        {pick.stake_pct != null && (
          <Figure
            value={pct(pick.stake_pct, 1)}
            label={
              bankroll ? `de la banca, unos ${money(pick.stake_pct * bankroll, currency)}` : "de la banca (Kelly fraccionado)"
            }
          />
        )}
        {pick.fair_odds != null && <Figure value={odds(pick.fair_odds)} label="cuota justa" />}
        {past && <Figure value={resultText(pick.result)} label="resultado" />}
        {past && pick.clv != null && <Figure value={signedPct(pick.clv)} label="CLV" />}
      </div>

      {(reasons.length > 0 || evaluarHref) && (
        <div className="flex flex-wrap items-end justify-between gap-4 border-t border-regla-suave px-5 py-4 sm:px-6">
          <ul className="space-y-0.5 text-nota text-grafito">
            {reasons.map((r) => (
              <li key={r}>{r}</li>
            ))}
          </ul>
          {evaluarHref && !past && (
            <Link href={evaluarHref} className="inline-flex min-h-10 items-center text-interfaz font-semibold text-boli underline underline-offset-4">
              Comprobar la cuota de Betano
            </Link>
          )}
        </div>
      )}
    </article>
  );
}

function NoPick({ note, past }: { note: string | null; past: boolean }) {
  return (
    <article aria-labelledby="apuesta-del-dia" className="rounded-[4px] border border-regla bg-hoja px-5 py-5 sm:px-6">
      <h2 id="apuesta-del-dia" className="semi text-interfaz font-bold text-grafito">
        Apuesta del día
      </h2>
      <div className="mt-2 flex flex-col items-start gap-x-6 gap-y-2 sm:flex-row sm:items-center">
        <div className="relative shrink-0 px-3">
          <PenMark kind="slash" className="inset-0 h-full w-full" />
          <p className="cond num text-[3.4rem] leading-none font-extrabold text-regla" aria-hidden>
            0.00
          </p>
        </div>
        <div className="min-w-0">
          <p className="cond text-[1.9rem] leading-tight font-bold">
            {past ? "Ese día no hubo apuesta del día" : "Hoy no hay apuesta del día"}
          </p>
          <p className="mt-1 max-w-[56ch] text-grafito">
            {note
              ? note.replace(/^Hoy no hay apuesta del día: /, "").replace(/^./, (c) => c.toUpperCase())
              : "Ninguna apuesta superó los umbrales de valor y confianza."}
          </p>
        </div>
      </div>
    </article>
  );
}

/** Recuento del día: cuántos partidos, cuántas cuotas con valor y cuántas pasan el corte */
function DayCount({ report }: { report: PicksReport }) {
  const n = report.matches?.length ?? 0;
  const value = report.value_bets.length;
  const pass = report.value_bets.filter((v) => "qualifies" in v && v.qualifies).length;
  const props = report.props_to_check?.length ?? 0;
  const items = [
    { v: n, l: n === 1 ? "partido analizado" : "partidos analizados" },
    { v: value, l: value === 1 ? "cuota con valor" : "cuotas con valor" },
    { v: pass, l: pass === 1 ? "pasa el corte" : "pasan el corte" },
    { v: props, l: "props para revisar" },
  ];
  return (
    <ul className="mt-5 grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-4">
      {items.map((x) => (
        <li key={x.l}>
          <span className="cond num block text-[1.75rem] leading-none font-bold">{x.v}</span>
          <span className="mt-1 block text-nota text-grafito">{x.l}</span>
        </li>
      ))}
    </ul>
  );
}

function MarginNote() {
  return (
    <aside className="border-l-2 border-boli/50 pl-5 text-interfaz leading-relaxed text-grafito lg:self-start">
      <h2 className="semi mb-2 text-base font-bold text-tinta">Antes de apostar</h2>
      <p>
        El backtest de 2024-25 y 2025-26 muestra que el modelo <strong className="text-tinta">no le gana a bet365</strong>{" "}
        en 1X2, goles ni hándicap asiático. Trata estas apuestas como candidatas para revisar, no como ganancia segura.
      </p>
      <p className="mt-2">
        Donde más margen puede haber es en props: remates, tarjetas según el árbitro y noticias de alineaciones que el
        mercado aún no recoge.
      </p>
      <p className="mt-2">
        La apuesta del día es la de mayor valor por confianza entre las que pasan el corte. Algunos días no hay ninguna.
      </p>
    </aside>
  );
}

// --------------------------------------------------------------------------- tablas

const th = "py-2 pr-4 text-left text-nota font-medium text-grafito";
const td = "py-2.5 pr-4 align-middle";

function isLive(row: ValueBet | PastValueBet): row is ValueBet {
  return "prob" in row;
}

function ValueBets({ rows }: { rows: (ValueBet | PastValueBet)[] }) {
  const [all, setAll] = useState(false);
  if (rows.length === 0) return <Empty>No hay cuotas con valor positivo para este día.</Empty>;
  const shown = all ? rows : rows.slice(0, 12);
  const live = isLive(rows[0]);
  return (
    <>
      <ul className="divide-y divide-regla-suave border-y border-regla-suave md:hidden">
        {shown.map((r, i) => {
          const [home, away] = splitMatch(r.match);
          return (
            <li key={i} className="py-3">
              <div className="flex items-start justify-between gap-4">
                <span className="font-semibold">{betLabel(r.market, r.selection, r.line, { home, away })}</span>
                <span className="cond num text-2xl leading-none font-bold">{odds(r.odds)}</span>
              </div>
              <p className="mt-0.5 text-nota text-grafito">
                {isLive(r) ? (
                  <Link href={`/partidos/${r.match_id}`} className="underline decoration-regla underline-offset-2">
                    {r.match}
                  </Link>
                ) : (
                  r.match
                )}
                {isLive(r) && `, en ${bookmakerName(r.bookmaker)}`}
              </p>
              {isLive(r) && (
                <div className="mt-2">
                  <EdgeBar prob={r.prob} odds={r.odds} compact />
                </div>
              )}
              <p className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-nota">
                <span>
                  Valor <strong className={`num ${r.ev > 0 ? "text-boli" : "text-rojo"}`}>{signedPct(r.ev)}</strong>
                </span>
                {isLive(r) ? (
                  <>
                    <span>
                      Confianza <strong className="num">{pct(r.confidence)}</strong>
                    </span>
                    {r.qualifies ? <Tag tone="boli">Pasa el corte</Tag> : <Tag>No llega al corte</Tag>}
                  </>
                ) : (
                  <span>{resultText(r.result)}</span>
                )}
              </p>
            </li>
          );
        })}
      </ul>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[720px] border-collapse text-interfaz">
          <thead className="border-b border-regla">
            <tr>
              <th className={th}>Partido</th>
              <th className={th}>Apuesta</th>
              <th className={`${th} text-right`}>Cuota</th>
              {live && <th className={`${th} w-40`}>Margen</th>}
              <th className={`${th} text-right`}>Valor</th>
              {live ? <th className={`${th} text-right`}>Confianza</th> : <th className={th}>Resultado</th>}
              {live && <th className={th}>Corte</th>}
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => {
              const [home, away] = splitMatch(r.match);
              return (
                <tr key={i} className="border-b border-regla-suave">
                  <td className={`${td} max-w-56`}>
                    {isLive(r) ? (
                      <Link href={`/partidos/${r.match_id}`} className="hover:text-boli hover:underline">
                        {r.match}
                      </Link>
                    ) : (
                      r.match
                    )}
                  </td>
                  <td className={td}>
                    {betLabel(r.market, r.selection, r.line, { home, away })}
                    {isLive(r) && <span className="block text-nota text-grafito">{bookmakerName(r.bookmaker)}</span>}
                  </td>
                  <td className={`${td} num cond text-right text-lg font-bold`}>{odds(r.odds)}</td>
                  {isLive(r) && (
                    <td className={td}>
                      <EdgeBar prob={r.prob} odds={r.odds} compact />
                    </td>
                  )}
                  <td className={`${td} num text-right font-semibold ${r.ev > 0 ? "text-boli" : "text-rojo"}`}>
                    {signedPct(r.ev)}
                  </td>
                  {isLive(r) ? (
                    <td className={`${td} num text-right`}>{pct(r.confidence)}</td>
                  ) : (
                    <td className={td}>{resultText(r.result)}</td>
                  )}
                  {isLive(r) && (
                    <td className={td}>{r.qualifies ? <Tag tone="boli">Pasa</Tag> : <Tag>No llega</Tag>}</td>
                  )}
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {rows.length > 12 && (
        <button type="button" onClick={() => setAll(!all)} className="mt-1 inline-flex min-h-10 items-center text-interfaz font-semibold text-boli underline underline-offset-4">
          {all ? "Mostrar menos" : `Mostrar las ${rows.length}`}
        </button>
      )}
    </>
  );
}

function Props({ rows }: { rows: PropMinOdds[] }) {
  const [all, setAll] = useState(false);
  if (rows.length === 0) return <Empty>No hay props que revisar para este día.</Empty>;
  const sorted = [...rows].sort((a, b) => b.prob - a.prob);
  const shown = all ? sorted : sorted.slice(0, 12);
  return (
    <>
      <ul className="divide-y divide-regla-suave border-y border-regla-suave md:hidden">
        {shown.map((r, i) => {
          const [home, away] = splitMatch(r.match ?? "");
          return (
            <li key={i} className="flex items-start justify-between gap-4 py-3">
              <div className="min-w-0">
                <p className="font-semibold">{betLabel(r.market, r.selection, r.line, { home, away, player: r.player })}</p>
                <p className="mt-0.5 text-nota text-grafito">
                  {r.match}. Probabilidad {pct(r.prob)}, cuota justa {odds(r.fair_odds)}
                </p>
              </div>
              <div className="shrink-0 text-right">
                <p className="cond num text-2xl leading-none font-bold text-boli">{odds(r.min_odds)}</p>
                <p className="text-etiqueta text-grafito">mínima</p>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[640px] border-collapse text-interfaz">
          <thead className="border-b border-regla">
            <tr>
              <th className={th}>Partido</th>
              <th className={th}>Apuesta</th>
              <th className={`${th} text-right`}>Probabilidad</th>
              <th className={`${th} text-right`}>Cuota justa</th>
              <th className={`${th} text-right`}>Cuota mínima</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => {
              const [home, away] = splitMatch(r.match ?? "");
              return (
                <tr key={i} className="border-b border-regla-suave">
                  <td className={`${td} max-w-56`}>
                    {r.match_id ? (
                      <Link href={`/partidos/${r.match_id}`} className="hover:text-boli hover:underline">
                        {r.match}
                      </Link>
                    ) : (
                      r.match
                    )}
                  </td>
                  <td className={td}>{betLabel(r.market, r.selection, r.line, { home, away, player: r.player })}</td>
                  <td className={`${td} num text-right`}>{pct(r.prob)}</td>
                  <td className={`${td} num text-right text-grafito`}>{odds(r.fair_odds)}</td>
                  <td className={`${td} num cond text-right text-lg font-bold text-boli`}>{odds(r.min_odds)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {rows.length > 12 && (
        <button type="button" onClick={() => setAll(!all)} className="mt-1 inline-flex min-h-10 items-center text-interfaz font-semibold text-boli underline underline-offset-4">
          {all ? "Mostrar menos" : `Mostrar las ${rows.length}`}
        </button>
      )}
    </>
  );
}

function DayMatches({ rows }: { rows: DayMatch[] }) {
  if (rows.length === 0) return <Empty>No hay partidos de las cuatro competiciones este día.</Empty>;
  return (
    <ul className="divide-y divide-regla-suave border-y border-regla-suave">
      {rows.map((m) => (
        <li key={m.match_id}>
          <Link
            href={`/partidos/${m.match_id}`}
            className="grid grid-cols-[3.5rem_1fr] gap-x-4 gap-y-2 py-3.5 hover:bg-hoja sm:grid-cols-[4rem_minmax(0,1.3fr)_minmax(0,1fr)_11rem] sm:items-center"
          >
            <span className="cond num text-2xl font-bold">{m.kickoff_local}</span>
            <span className="min-w-0">
              <span className="semi block truncate text-[1.05rem] font-semibold">
                <Crest id={m.home_id} size={18} className="mr-1.5 -mt-0.5" />
                {m.home} <span className="font-normal text-grafito">vs</span>{" "}
                <Crest id={m.away_id} size={18} className="mr-1.5 -mt-0.5" />
                {m.away}
              </span>
              {/* En el celular la etiqueta va junto a la competición, en vez de en una fila propia */}
              <span className="flex flex-wrap items-center gap-x-2 gap-y-1 text-nota text-grafito">
                {competitionName(m.competition)}
                <Tag tone={m.stage === "confirmed" ? "confirmada" : "neutral"} className="sm:hidden">
                  {stageText(m.stage)}
                </Tag>
              </span>
            </span>
            <span className="col-start-2 sm:col-start-auto">
              <TriBar probs={m["1x2"]} home={m.home} away={m.away} />
              <span className="num mt-1 flex justify-between text-nota text-grafito">
                <span>{pct(m["1x2"].home)}</span>
                <span>{pct(m["1x2"].draw)}</span>
                <span>{pct(m["1x2"].away)}</span>
              </span>
            </span>
            <span className="hidden sm:flex">
              <Tag tone={m.stage === "confirmed" ? "confirmada" : "neutral"} className="sm:w-full sm:justify-center">
                {stageText(m.stage)}
              </Tag>
            </span>
          </Link>
        </li>
      ))}
    </ul>
  );
}
