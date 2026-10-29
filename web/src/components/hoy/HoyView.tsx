"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Fragment, useCallback, useState } from "react";
import { AlertList, AlertTags } from "@/components/Avisos";
import { CaptureDrop } from "@/components/capturas/CaptureDrop";
import { Crest } from "@/components/Crest";
import { PickRecord } from "@/components/PickRecord";
import { PorQueFallo } from "@/components/PorQueFallo";
import { AlertTag } from "@/components/semana/Radar";
import { Tabs, useHashTab } from "@/components/Tabs";
import { Button, EdgeBar, Empty, ErrorNote, Figure, Loading, Section, Tag } from "@/components/ui";
import { api, type ApiError, useApi } from "@/lib/api";
import {
  competitionName,
  longDay,
  money,
  odds,
  pct,
  RESULT_TONE,
  resultText,
  shiftDay,
  signedPct,
  splitMatch,
  stageText,
} from "@/lib/format";
import { useRemembered, useToday } from "@/lib/hooks";
import { useMe } from "@/lib/me";
import { betLabel, bookmakerName } from "@/lib/markets";
import type { Capture, DayMatch, PastValueBet, Performance, PickOfDay, PicksReport, PropMinOdds, ValueBet } from "@/lib/types";

function dayTitle(day: string, today: string): string {
  if (day === today) return "Hoy";
  if (day === shiftDay(today, 1)) return "Mañana";
  if (day === shiftDay(today, -1)) return "Ayer";
  const d = longDay(day);
  return d.charAt(0).toUpperCase() + d.slice(1);
}

// Los partidos van en «La jornada», al lado del titular; las dos listas largas, en pestañas
const TABS = [
  { id: "valor", label: "Con valor" },
  { id: "props", label: "Props" },
] as const;

const dayLink =
  "inline-flex h-10 items-center border border-tinta bg-hoja px-3 text-interfaz font-bold transition-colors hover:bg-tinta hover:text-papel";

export function HoyView() {
  const params = useSearchParams();
  const today = useToday();
  const day = params.get("dia") ?? today;
  const { data, error, isLoading, mutate } = useApi<PicksReport>(day ? `/picks?day=${day}` : null);
  const { data: perf } = useApi<Performance>("/performance");
  const { me } = useMe();
  const [recalc, setRecalc] = useState<{ busy: boolean; error?: ApiError }>({ busy: false });
  const past = !!day && !!today && day < today;

  // Los días pasados solo guardan las apuestas con valor: sin partidos ni props no hacen falta pestañas
  const matches = !past ? data?.matches : undefined;
  const props = !past ? data?.props_to_check : undefined;
  const counts: Record<string, number | undefined> = {
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
      <Link href={`/?dia=${shiftDay(day, -1)}${keep}`} className={dayLink}>
        Día anterior
      </Link>
      <Link href={`/?dia=${shiftDay(day, 1)}${keep}`} className={dayLink}>
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

  const title = day && today ? dayTitle(day, today) : "Hoy";
  const near = !!day && !!today && Math.abs(Date.parse(day) - Date.parse(today)) <= 864e5;

  return (
    <>
      {/* Tira de la edición: qué día es y cómo moverse entre días */}
      <div className="flex flex-wrap items-center justify-between gap-x-6 gap-y-3 border-b border-regla pb-3">
        <div className="min-w-0">
          <h1 className="semi text-xl leading-tight font-bold">
            {title}
            {day && near && <span className="font-medium text-grafito">, {longDay(day)}</span>}
          </h1>
          {past ? (
            <p className="text-nota text-grafito">Lo que se guardó ese día.</p>
          ) : (
            data?.matches && <DayCount report={data} />
          )}
        </div>
        <div className="flex flex-wrap items-center gap-2">{nav}</div>
      </div>
      {recalc.error && (
        <div className="mt-6">
          <ErrorNote error={recalc.error} />
        </div>
      )}

      <div className="grid gap-x-10 gap-y-10 pt-6 pb-10 lg:grid-cols-[minmax(0,1fr)_340px] lg:grid-rows-[auto_1fr]">
        <div className="min-w-0">
          {error ? (
            <ErrorNote error={error} onRetry={() => mutate()} />
          ) : !data ? (
            <div className="border-t-[3px] border-tinta pt-6">
              <Loading lines={4} label="Calculando las apuestas del día" />
            </div>
          ) : data.pick_of_day ? (
            <Slip pick={data.pick_of_day} past={past} bankroll={perf?.bankroll.bankroll} currency={perf?.bankroll.currency} />
          ) : (
            <NoPick note={data.notes?.find((n) => n.startsWith("Hoy no hay")) ?? null} past={past} />
          )}
          {data?.notes
            ?.filter((n) => !n.startsWith("Hoy no hay"))
            .map((n) => (
              <p key={n} className="mt-4 border-t-[3px] border-tarjeta bg-tarjeta-suave px-3 py-2 text-interfaz">
                {n}
              </p>
            ))}
        </div>
        <div className="min-w-0 space-y-10 lg:col-start-2 lg:row-span-2 lg:row-start-1">
          {matches && <Jornada rows={matches} />}
          <PickRecord />
          {!past && me?.ai_enabled !== false && <CaptureQuick />}
          <MarginNote />
        </div>

        {data && (
          <div className="min-w-0 lg:col-start-1">
            {tabs.length > 1 ? (
              <Tabs tabs={tabs} current={tab} onSelect={setTab} label="Listas del día">
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
            )}
          </div>
        )}
      </div>
    </>
  );
}

function ValueSection({ rows, past }: { rows: (ValueBet | PastValueBet)[]; past: boolean }) {
  const [order, setOrder] = useRemembered("apuestas.orden-valor", ORDER_IDS);
  return (
    <Section
      title="Otras apuestas con valor"
      actions={rows.length > 1 ? <OrderPicker value={order} onChange={setOrder} /> : undefined}
      intro={
        past
          ? "Las que el sistema guardó ese día con valor positivo, con su resultado. Puedes ver primero las que pasaron el corte, las más probables, las de más confianza o las de más valor. No salen las cuotas de menos de 1.20."
          : "Cuotas de bet365 y Betano donde nuestra estimación supera lo que implica la cuota. Las que pasan el corte de valor, probabilidad y confianza se guardan y, cuando termina el partido, se anota si se ganaron o se perdieron; entre ellas sale la apuesta del día. «Más probables» ordena por la probabilidad de que salga; «Más confianza», por lo seguro que está el modelo de su estimación. No salen las cuotas de menos de 1.20, que casi no dejan margen."
      }
    >
      <PickRecord variant="line" source="corte" />
      <ValueBets rows={rows} order={order} />
    </Section>
  );
}

// Orden de «Otras apuestas con valor»; se recuerda en el navegador
const ORDERS = [
  { id: "corte", label: "Pasan el corte" },
  { id: "probable", label: "Más probables" },
  { id: "confianza", label: "Más confianza" },
  { id: "valor", label: "Más valor" },
] as const;
type Order = (typeof ORDERS)[number]["id"];
const ORDER_IDS = ORDERS.map((o) => o.id);

function OrderPicker({ value, onChange }: { value: Order; onChange: (v: Order) => void }) {
  return (
    <fieldset className="flex flex-wrap gap-1">
      <legend className="sr-only">Ordenar las apuestas con valor</legend>
      {ORDERS.map((o) => (
        <button
          key={o.id}
          type="button"
          aria-pressed={value === o.id}
          onClick={() => onChange(o.id)}
          className={`h-9 border px-3 text-interfaz font-semibold ${
            value === o.id ? "border-tinta bg-tinta text-papel" : "border-regla bg-hoja text-grafito hover:text-tinta"
          }`}
        >
          {o.label}
        </button>
      ))}
    </fieldset>
  );
}

/** Primero las que pasan el corte (por valor), o todas por probabilidad, confianza o valor esperado */
function sortRows(rows: (ValueBet | PastValueBet)[], order: Order): (ValueBet | PastValueBet)[] {
  const key: Record<Order, (r: ValueBet | PastValueBet) => number> = {
    corte: (r) => r.ev,
    probable: (r) => r.prob ?? -1,
    confianza: (r) => r.confidence ?? -1,
    valor: (r) => r.ev,
  };
  return [...rows].sort(
    (a, b) => (order === "corte" ? Number(passes(b)) - Number(passes(a)) : 0) || key[order](b) - key[order](a),
  );
}

// --------------------------------------------------------------------------- capturas

/** Atajo para revisar una cuota vista en la casa de apuestas: se sube y se abre en Capturas */
function CaptureQuick() {
  const router = useRouter();
  const onUploaded = useCallback((c: Capture) => router.push(`/capturas?nueva=${c.id}`), [router]);
  return (
    <div className="border-t-[3px] border-tinta pt-3">
      <h2 className="cond mb-2 text-lateral leading-none font-black uppercase">¿Viste una cuota?</h2>
      <p className="mb-3 text-nota text-grafito">
        Sube o pega la captura de Betano o bet365: una IA la lee y el modelo te dice si tiene valor.
      </p>
      <CaptureDrop onUploaded={onUploaded} compact />
    </div>
  );
}

// --------------------------------------------------------------------------- apuesta del día

// La apuesta del día es el titular de la portada; sus cifras, la ficha
const headline = "cond text-titular leading-[0.88] font-black tracking-[-0.01em] text-balance uppercase";
const deck = "mt-4 max-w-[62ch] text-entradilla leading-snug font-medium";

function Slip({ pick, past, bankroll, currency }: { pick: PickOfDay; past: boolean; bankroll?: number; currency?: string }) {
  const [home, away] = splitMatch(pick.match);
  const label = betLabel(pick.market, pick.selection, pick.line, { home, away });
  const reasons = (pick.reasons ?? []).filter((r) => !r.startsWith("pick_id="));
  const evaluarHref = pick.match_id
    ? `/evaluar?partido=${pick.match_id}&mercado=${pick.market}&seleccion=${pick.selection}${pick.line != null ? `&linea=${pick.line}` : ""}`
    : null;
  const figures: { value: string; label: string; tone?: "boli" | "rojo" }[] = [
    ...(pick.prob != null ? [{ value: pct(pick.prob), label: "probabilidad" }] : []),
    ...(pick.fair_odds != null ? [{ value: odds(pick.fair_odds), label: "cuota justa" }] : []),
    { value: signedPct(pick.ev), label: "valor esperado", tone: pick.ev > 0 ? ("boli" as const) : ("rojo" as const) },
    ...(pick.confidence != null ? [{ value: pct(pick.confidence), label: "confianza" }] : []),
    ...(pick.stake_pct != null
      ? [
          {
            value: pct(pick.stake_pct, 1),
            label: bankroll ? `de la banca, unos ${money(pick.stake_pct * bankroll, currency)}` : "de la banca (Kelly fraccionado)",
          },
        ]
      : []),
    ...(past ? [{ value: resultText(pick.result), label: "resultado" }] : []),
    ...(past && pick.clv != null ? [{ value: signedPct(pick.clv), label: "CLV" }] : []),
  ];

  return (
    <article aria-labelledby="apuesta-del-dia">
      <h2 id="apuesta-del-dia" className={headline}>
        <span className="sr-only">Apuesta del día: </span>
        {label}
      </h2>
      <p className={deck}>
        <span className="mr-2 inline-block bg-rojo-portada px-2 align-[0.12em] text-nota leading-6 font-extrabold tracking-[0.08em] text-white uppercase">
          Apuesta del día
        </span>
        {pick.match_id ? (
          <Link href={`/partidos/${pick.match_id}`} className="font-bold underline decoration-regla underline-offset-4 hover:decoration-tinta">
            <Crest id={pick.home_id} size={22} className="mr-1.5 -mt-1" />
            {home} vs <Crest id={pick.away_id} size={22} className="mr-1.5 -mt-1" />
            {away}
          </Link>
        ) : (
          <strong>{pick.match}</strong>
        )}
        {pick.competition && `, ${pick.competition}`}
        {pick.kickoff_local && <span className="num">, {pick.kickoff_local.slice(11)}</span>}.{" "}
        {pick.stage && `${stageText(pick.stage)}. `}
        {pick.prob != null && (
          <>
            El modelo le da un <strong className="num">{pct(pick.prob)}</strong>; la cuota implica un{" "}
            <strong className="num">{pct(1 / pick.odds)}</strong>.
          </>
        )}
      </p>

      <div className="mt-6 grid grid-cols-2 items-end gap-x-9 gap-y-5 border-t-[3px] border-b border-tinta py-4 sm:flex sm:flex-wrap">
        <div className="col-span-2">
          <p className="cond num text-cuota leading-none font-black">
            <span className="resalte inline-block px-2 pt-1 leading-[0.85]">{odds(pick.odds)}</span>
          </p>
          <p className="mt-2 text-nota leading-snug text-grafito">cuota{pick.bookmaker ? ` en ${bookmakerName(pick.bookmaker)}` : ""}</p>
        </div>
        {figures.map((f) => (
          <Figure key={f.label} value={f.value} label={f.label} tone={f.tone} />
        ))}
      </div>

      {reasons.length > 0 && (
        <ul className="mt-5 grid gap-x-8 gap-y-2 text-interfaz sm:grid-cols-2">
          {reasons.map((r) => (
            <li key={r} className="flex gap-2.5">
              <span aria-hidden className="mt-[0.5em] size-2 shrink-0 bg-amarillo ring-1 ring-tinta" />
              {r}
            </li>
          ))}
        </ul>
      )}
      {!past && <AlertList alerts={pick.alerts} className="mt-5" />}
      {past && pick.pick_id && (pick.result === "loss" || pick.result === "half_loss") && <PorQueFallo pickId={pick.pick_id} />}
      {evaluarHref && !past && (
        <Link href={evaluarHref} className="mt-4 inline-flex min-h-10 items-center text-interfaz font-bold text-boli underline underline-offset-4">
          Comprobar la cuota de Betano
        </Link>
      )}
    </article>
  );
}

function NoPick({ note, past }: { note: string | null; past: boolean }) {
  return (
    <article aria-labelledby="apuesta-del-dia">
      <h2 id="apuesta-del-dia" className={headline}>
        {past ? "Ese día no hubo apuesta del día" : "Hoy no hay apuesta del día"}
      </h2>
      <p className={deck}>
        {note
          ? note.replace(/^Hoy no hay apuesta del día: /, "").replace(/^./, (c) => c.toUpperCase())
          : "Ninguna apuesta superó los umbrales de valor y confianza."}
      </p>
    </article>
  );
}

/** Recuento del día en una línea: partidos, cuotas con valor, las que pasan el corte y props */
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
    <ul className="flex flex-wrap gap-x-4 text-nota text-grafito">
      {items.map((x) => (
        <li key={x.l}>
          <strong className="num font-bold text-tinta">{x.v}</strong> {x.l}
        </li>
      ))}
    </ul>
  );
}

/** Los partidos del día como la tabla de un diario: por competición, con el 1X2 del modelo */
// En el celular la jornada va antes de las apuestas con valor: se corta para no alejarlas
const JORNADA_MOBILE = 8;

function Jornada({ rows }: { rows: DayMatch[] }) {
  const [all, setAll] = useState(false);
  const groups: { comp: DayMatch["competition"]; rows: { m: DayMatch; i: number }[] }[] = [];
  rows.forEach((m, i) => {
    const g = groups.find((x) => x.comp === m.competition);
    if (g) g.rows.push({ m, i });
    else groups.push({ comp: m.competition, rows: [{ m, i }] });
  });
  const cut = (i: number) => (!all && i >= JORNADA_MOBILE ? "hidden lg:table-row" : "");
  return (
    <section aria-labelledby="jornada">
      <div className="flex items-baseline justify-between gap-4 border-t-[3px] border-tinta pt-3">
        <h2 id="jornada" className="cond text-seccion leading-none font-black uppercase">
          La jornada
        </h2>
        <span className="text-nota font-semibold text-grafito">1X2 del modelo, en %</span>
      </div>
      {rows.length === 0 ? (
        <Empty>No hay partidos de las seis competiciones este día.</Empty>
      ) : (
        <table className="w-full table-fixed border-collapse text-interfaz">
          <caption className="sr-only">Partidos del día con la probabilidad de local, empate y visitante</caption>
          <colgroup>
            <col className="w-12" />
            <col />
            <col className="w-9" />
            <col className="w-9" />
            <col className="w-9" />
          </colgroup>
          <thead>
            <tr className="text-nota text-grafito">
              <th scope="col" className="pt-1.5 text-left font-semibold">
                Hora
              </th>
              <th scope="col" className="pt-1.5 text-left font-semibold">
                <span className="sr-only">Partido</span>
              </th>
              <th scope="col" className="pt-1.5 text-right font-semibold">
                1
              </th>
              <th scope="col" className="pt-1.5 text-right font-semibold">
                X
              </th>
              <th scope="col" className="pt-1.5 text-right font-semibold">
                2
              </th>
            </tr>
          </thead>
          {groups.map((g) => (
            <tbody key={g.comp}>
              <tr className={cut(g.rows[0].i)}>
                <th colSpan={5} scope="colgroup" className="pt-3 pb-1 text-left text-nota font-extrabold tracking-[0.06em] uppercase">
                  {competitionName(g.comp)}
                </th>
              </tr>
              {g.rows.map(({ m, i }) => {
                const p = [m["1x2"].home, m["1x2"].draw, m["1x2"].away];
                const top = Math.max(...p);
                return (
                  <tr key={m.match_id} className={`border-t border-regla-suave ${cut(i)}`}>
                    <td className="num py-2 align-top font-bold">{m.kickoff_local}</td>
                    <td className="py-2 pr-2">
                      <Link href={`/partidos/${m.match_id}`} className="block leading-snug font-semibold hover:underline">
                        <span className="block truncate">
                          <Crest id={m.home_id} size={16} className="mr-1.5 -mt-0.5" />
                          {m.home}
                        </span>
                        <span className="block truncate">
                          <Crest id={m.away_id} size={16} className="mr-1.5 -mt-0.5" />
                          {m.away}
                        </span>
                      </Link>
                      {(m.stage === "confirmed" || !!m.alerts?.length) && (
                        <span className="mt-1 flex flex-wrap gap-1">
                          {m.stage === "confirmed" && <Tag tone="confirmada">{stageText(m.stage)}</Tag>}
                          {m.alerts?.map((a) => (
                            <AlertTag key={a.team_id} alert={a} />
                          ))}
                        </span>
                      )}
                    </td>
                    {p.map((x, i) => (
                      <td
                        key={i}
                        className={`cond num py-2 text-right text-destacado leading-none ${x === top ? "font-black" : "font-semibold text-grafito"}`}
                      >
                        {Math.round(x * 100)}
                      </td>
                    ))}
                  </tr>
                );
              })}
            </tbody>
          ))}
        </table>
      )}
      {rows.length > JORNADA_MOBILE && (
        <button
          type="button"
          onClick={() => setAll(!all)}
          className="mt-1 inline-flex min-h-10 items-center text-interfaz font-bold text-boli underline underline-offset-4 lg:hidden"
        >
          {all ? "Mostrar menos" : `Mostrar los ${rows.length}`}
        </button>
      )}
    </section>
  );
}

function MarginNote() {
  return (
    <aside className="border border-regla bg-negro p-5 text-interfaz leading-relaxed text-white/85">
      <h2 className="cond mb-2 text-lateral leading-none font-black text-amarillo uppercase">Antes de apostar</h2>
      <p>
        El backtest de 2024-25 y 2025-26 muestra que el modelo <strong className="text-white">no le gana a bet365</strong> en
        1X2, goles ni hándicap asiático. Trata estas apuestas como candidatas para revisar, no como ganancia segura.
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

const th = "py-2 pr-4 text-left text-nota font-semibold text-grafito";
const td = "py-2.5 pr-4 align-middle";

function isLive(row: ValueBet | PastValueBet): row is ValueBet {
  return !("status" in row);
}

/** Pasa el corte; en un día pasado, la que se retiró antes del partido ya no cuenta */
function passes(row: ValueBet | PastValueBet): boolean {
  return isLive(row) ? row.qualifies : !!row.qualifies && row.status !== "withdrawn";
}

/** Resultado de una guardada: retirada antes del partido, pendiente o cómo terminó */
function PastResult({ row }: { row: PastValueBet }) {
  if (row.status === "withdrawn") return <Tag>Retirada</Tag>;
  return <Tag tone={row.result ? (RESULT_TONE[row.result] ?? "neutral") : "tarjeta"}>{resultText(row.result)}</Tag>;
}

/** CLV de una guardada: su cuota frente a la justa de Pinnacle (o el cierre de bet365) antes del partido */
function PastClv({ row }: { row: PastValueBet }) {
  if (row.clv == null) return null;
  return (
    <span className={`num ${row.clv > 0 ? "text-boli" : row.clv < 0 ? "text-rojo" : ""}`}>CLV {signedPct(row.clv)}</span>
  );
}

/** Corte: «Pasa» en azul y «No llega» en gris, siempre con su palabra */
function CutTag({ row, short = false }: { row: ValueBet | PastValueBet; short?: boolean }) {
  const live = isLive(row);
  if (passes(row)) {
    return <Tag tone="boli">{short ? (live ? "Pasa" : "Pasó") : live ? "Pasa el corte" : "Pasó el corte"}</Tag>;
  }
  return <Tag>{short ? (live ? "No llega" : "No llegó") : live ? "No llega al corte" : "No llegó al corte"}</Tag>;
}

function ValueBets({ rows: input, order }: { rows: (ValueBet | PastValueBet)[]; order: Order }) {
  const [all, setAll] = useState(false);
  // Apuesta con el aviso del radar abierto, por su identidad (el índice cambia al reordenar o mostrar todas)
  const [open, setOpen] = useState<string | null>(null);
  const keyOf = (r: ValueBet | PastValueBet) => `${r.match}|${r.market}|${r.selection}|${r.line}|${"bookmaker" in r ? r.bookmaker : ""}`;
  const toggle = (r: ValueBet | PastValueBet) => setOpen(open === keyOf(r) ? null : keyOf(r));
  if (input.length === 0) return <Empty>No hay cuotas con valor positivo para este día.</Empty>;
  const rows = sortRows(input, order);
  const shown = all ? rows : rows.slice(0, 12);
  const live = isLive(rows[0]);
  // Con el orden «Pasan el corte», una línea separa las que no llegan
  const firstOut = order === "corte" ? shown.findIndex((r) => !passes(r)) : -1;
  const divider = firstOut > 0 ? firstOut : -1;
  return (
    <>
      <ul className="divide-y divide-regla-suave border-y border-regla-suave md:hidden">
        {shown.map((r, i) => {
          const [home, away] = splitMatch(r.match);
          return (
            <li key={i} className="py-3">
              {i === divider && <p className="mb-3 text-nota font-semibold text-grafito">No llegan al corte</p>}
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
              {isLive(r) && <AlertTags alerts={r.alerts} open={open === keyOf(r)} onToggle={() => toggle(r)} />}
              {isLive(r) && open === keyOf(r) && <AlertList alerts={r.alerts} className="mt-2" />}
              {isLive(r) && (
                <div className="mt-2">
                  <EdgeBar prob={r.prob} odds={r.odds} compact />
                </div>
              )}
              <p className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-nota">
                {r.prob != null && (
                  <span>
                    Prob. <strong className="num">{pct(r.prob)}</strong>
                  </span>
                )}
                <span>
                  Valor <strong className={`num ${r.ev > 0 ? "text-boli" : "text-rojo"}`}>{signedPct(r.ev)}</strong>
                </span>
                {r.confidence != null && (
                  <span>
                    Confianza <strong className="num">{pct(r.confidence)}</strong>
                  </span>
                )}
                <CutTag row={r} />
                {!isLive(r) && <PastResult row={r} />}
                {!isLive(r) && <PastClv row={r} />}
              </p>
            </li>
          );
        })}
      </ul>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[800px] border-collapse text-interfaz">
          <thead className="border-b border-tinta">
            <tr>
              <th className={th}>Partido</th>
              <th className={th}>Apuesta</th>
              <th className={`${th} text-right`}>Cuota</th>
              {live && <th className={`${th} w-40`}>Margen</th>}
              <th className={`${th} text-right`}>Prob.</th>
              <th className={`${th} text-right`}>Valor</th>
              <th className={`${th} text-right`}>Confianza</th>
              {!live && <th className={th}>Resultado</th>}
              <th className={th}>Corte</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r, i) => {
              const [home, away] = splitMatch(r.match);
              return (
                <Fragment key={i}>
                  {i === divider && (
                    <tr>
                      <td colSpan={8} className="pt-5 pb-2 text-nota font-semibold text-grafito">
                        No llegan al corte
                      </td>
                    </tr>
                  )}
                  <tr className="border-b border-regla-suave">
                    <td className={`${td} max-w-56`}>
                      {isLive(r) ? (
                        <Link href={`/partidos/${r.match_id}`} className="hover:text-boli hover:underline">
                          {r.match}
                        </Link>
                      ) : (
                        r.match
                      )}
                      {isLive(r) && <AlertTags alerts={r.alerts} open={open === keyOf(r)} onToggle={() => toggle(r)} />}
                    </td>
                    <td className={td}>
                      {betLabel(r.market, r.selection, r.line, { home, away })}
                      {isLive(r) && <span className="block text-nota text-grafito">{bookmakerName(r.bookmaker)}</span>}
                    </td>
                    <td className={`${td} num cond text-right text-xl font-extrabold`}>{odds(r.odds)}</td>
                    {isLive(r) && (
                      <td className={td}>
                        <EdgeBar prob={r.prob} odds={r.odds} compact />
                      </td>
                    )}
                    <td className={`${td} num text-right`}>{pct(r.prob)}</td>
                    <td className={`${td} num text-right font-semibold ${r.ev > 0 ? "text-boli" : "text-rojo"}`}>
                      {signedPct(r.ev)}
                    </td>
                    <td className={`${td} num text-right`}>{pct(r.confidence)}</td>
                    {!isLive(r) && (
                      <td className={td}>
                        <PastResult row={r} />
                        <span className="block text-nota">
                          <PastClv row={r} />
                        </span>
                      </td>
                    )}
                    <td className={td}>
                      <CutTag row={r} short />
                    </td>
                  </tr>
                  {isLive(r) && open === keyOf(r) && (
                    <tr className="border-b border-regla-suave">
                      <td colSpan={8} className="pt-1 pb-3">
                        <AlertList alerts={r.alerts} />
                      </td>
                    </tr>
                  )}
                </Fragment>
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
          <thead className="border-b border-tinta">
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
                  <td className={`${td} num cond text-right text-xl font-extrabold text-boli`}>{odds(r.min_odds)}</td>
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
