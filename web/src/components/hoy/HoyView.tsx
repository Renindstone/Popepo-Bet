"use client";

import Link from "next/link";
import { useRouter, useSearchParams } from "next/navigation";
import { Fragment, useCallback, useState } from "react";
import { AlertList, AlertTags } from "@/components/Avisos";
import { CaptureDrop } from "@/components/capturas/CaptureDrop";
import { Comparador } from "@/components/hoy/Comparador";
import { Crest } from "@/components/Crest";
import { PickRecord } from "@/components/PickRecord";
import { PorQueFallo } from "@/components/PorQueFallo";
import { RivalryTag } from "@/components/Rivalry";
import { UnusualTag } from "@/components/Unusual";
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
import { tr } from "@/lib/i18n";
import { useMe } from "@/lib/me";
import { betLabel, bookmakerName } from "@/lib/markets";
import type {
  Capture,
  DayMatch,
  PastValueBet,
  Performance,
  PickOfDay,
  PicksReport,
  PriceComparison,
  PropMinOdds,
  ValueBet,
} from "@/lib/types";

function dayTitle(day: string, today: string): string {
  if (day === today) return tr("Hoy", "Today");
  if (day === shiftDay(today, 1)) return tr("Mañana", "Tomorrow");
  if (day === shiftDay(today, -1)) return tr("Ayer", "Yesterday");
  const d = longDay(day);
  return d.charAt(0).toUpperCase() + d.slice(1);
}

// Los partidos van en «La jornada», al lado del titular; las dos listas largas, en pestañas
const tabDefs = () => [
  { id: "valor", label: tr("Con valor", "With value") },
  { id: "props", label: "Props" },
  { id: "precio", label: tr("Frente a Pinnacle", "Against Pinnacle") },
];

// La nota del día sin apuesta llega de la API en el idioma del panel
const isNoPickNote = (n: string) => /^(Hoy no hay|No bet of the day)/.test(n);

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
  // Comparar precios solo tiene sentido con partidos por jugar
  const compare = useApi<PriceComparison>(day && today && !past ? `/compare?day=${day}` : null);

  // Los días pasados solo guardan las apuestas con valor: sin partidos ni props no hacen falta pestañas
  const matches = !past ? data?.matches : undefined;
  const props = !past ? data?.props_to_check : undefined;
  const counts: Record<string, number | undefined> = {
    valor: data?.value_bets.length,
    props: props?.length,
    precio: compare.data?.rows.length ?? (compare.error ? 0 : undefined),
  };
  const tabs = tabDefs().filter((t) => t.id === "valor" || counts[t.id] != null).map((t) => ({ ...t, count: counts[t.id] }));
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
        {tr("Día anterior", "Previous day")}
      </Link>
      <Link href={`/?dia=${shiftDay(day, 1)}${keep}`} className={dayLink}>
        {tr("Día siguiente", "Next day")}
      </Link>
      {day !== today && (
        <Link href={`/${keep}`} className="inline-flex h-10 items-center px-2 text-interfaz font-semibold text-boli underline underline-offset-4">
          {tr("Volver a hoy", "Back to today")}
        </Link>
      )}
      {!past && (
        <Button onClick={recalculate} disabled={recalc.busy || isLoading}>
          {recalc.busy ? tr("Recalculando…", "Recalculating…") : tr("Recalcular", "Recalculate")}
        </Button>
      )}
    </>
  );

  const title = day && today ? dayTitle(day, today) : tr("Hoy", "Today");
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
            <p className="text-nota text-grafito">{tr("Lo que se guardó ese día.", "What was saved that day.")}</p>
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
              <Loading lines={4} label={tr("Calculando las apuestas del día", "Working out the day's bets")} />
            </div>
          ) : data.pick_of_day ? (
            <Slip pick={data.pick_of_day} past={past} bankroll={perf?.bankroll.bankroll} currency={perf?.bankroll.currency} />
          ) : (
            <NoPick note={data.notes?.find(isNoPickNote) ?? null} past={past} />
          )}
          {data?.notes
            ?.filter((n) => !isNoPickNote(n))
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
              <Tabs tabs={tabs} current={tab} onSelect={setTab} label={tr("Listas del día", "The day's lists")}>
                {tab === "valor" && <ValueSection rows={data.value_bets} past={past} />}
                {tab === "props" && props && (
                  <Section
                    title={tr("Props con cuota mínima", "Props with minimum odds")}
                    intro={tr(
                      "Mercados para los que no tenemos cuota. Si tu casa paga al menos la cuota mínima, el modelo ve un 5 % de valor. Sin un mercado afilado como referencia, el margen de error es mayor.",
                      "Markets we have no odds for. If your bookmaker pays at least the minimum odds, the model sees 5 % value. Without a sharp market as a reference, the margin of error is bigger.",
                    )}
                  >
                    <Props rows={props} />
                  </Section>
                )}
                {tab === "precio" && (
                  <Comparador data={compare.data} error={compare.error} onRetry={() => compare.mutate()} />
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
      title={tr("Otras apuestas con valor", "Other value bets")}
      actions={rows.length > 1 ? <OrderPicker value={order} onChange={setOrder} /> : undefined}
      intro={
        past
          ? tr(
              "Las que el sistema guardó ese día con valor positivo, con su resultado. Puedes ver primero las que pasaron el corte, las más probables, las de más confianza o las de más valor. Los días anteriores al 5 de noviembre de 2026 incluyen las de menos del 60 % de probabilidad. No salen las cuotas de menos de 1.20.",
              "The positive-value bets the system saved that day, with their result. You can see first the ones that passed the cut, the most likely, the most confident or the highest value. Days before 5 November 2026 include those under 60% probability. Odds under 1.20 are not shown.",
            )
          : tr(
              "Cuotas de bet365 y Betano con 60 % o más de probabilidad donde nuestra estimación supera lo que implica la cuota. Las que pasan el corte de valor, probabilidad y confianza se guardan y, cuando termina el partido, se anota si se ganaron o se perdieron; entre ellas sale la apuesta del día. «Más probables» ordena por la probabilidad de que salga; «Más confianza», por lo seguro que está el modelo de su estimación. No salen las cuotas de menos de 1.20, que casi no dejan margen.",
              "bet365 and Betano odds with a 60% or higher probability where our estimate beats what the odds imply. The ones that pass the value, probability and confidence cut are saved and, when the match ends, marked as won or lost; the bet of the day comes from them. “Most likely” sorts by the chance it lands; “Most confident”, by how sure the model is of its estimate. Odds under 1.20 are not shown, as they leave almost no margin.",
            )
      }
    >
      <PickRecord variant="line" source="corte" />
      <ValueBets rows={rows} order={order} />
    </Section>
  );
}

// Orden de «Otras apuestas con valor»; se recuerda en el navegador
const ORDER_IDS = ["corte", "probable", "confianza", "valor"] as const;
type Order = (typeof ORDER_IDS)[number];

function OrderPicker({ value, onChange }: { value: Order; onChange: (v: Order) => void }) {
  const orders: { id: Order; label: string }[] = [
    { id: "corte", label: tr("Pasan el corte", "Pass the cut") },
    { id: "probable", label: tr("Más probables", "Most likely") },
    { id: "confianza", label: tr("Más confianza", "Most confident") },
    { id: "valor", label: tr("Más valor", "Highest value") },
  ];
  return (
    <fieldset className="flex flex-wrap gap-1">
      <legend className="sr-only">{tr("Ordenar las apuestas con valor", "Sort the value bets")}</legend>
      {orders.map((o) => (
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
      <h2 className="cond mb-2 text-lateral leading-none font-black uppercase">{tr("¿Viste una cuota?", "Spotted some odds?")}</h2>
      <p className="mb-3 text-nota text-grafito">
        {tr(
          "Sube o pega la captura de Betano o bet365: una IA la lee y el modelo te dice si tiene valor.",
          "Upload or paste the Betano or bet365 screenshot: an AI reads it and the model tells you if it has value.",
        )}
      </p>
      <CaptureDrop onUploaded={onUploaded} compact />
    </div>
  );
}

/**
 * Evaluar cuota con la apuesta ya rellena. Con la cuota y la casa, Evaluar la calcula al abrir y deja registrarla ahí
 * mismo; sin ellas, sirve para escribir la cuota de otra casa.
 */
function evaluarHref(matchId: number, market: string, selection: string, line: number | null, odds?: number, bookmaker?: string) {
  const q = new URLSearchParams({ partido: String(matchId), mercado: market, seleccion: selection });
  if (line != null) q.set("linea", String(line));
  if (odds != null) q.set("cuota", String(odds));
  if (bookmaker) q.set("casa", bookmaker);
  return `/evaluar?${q}`;
}

// La apuesta en sí lleva a registrarla; los equipos, al análisis del partido
const betLink = "underline decoration-regla underline-offset-4 hover:decoration-tinta";

// --------------------------------------------------------------------------- apuesta del día

// La apuesta del día es el titular de la portada; sus cifras, la ficha
const headline = "cond text-titular leading-[0.88] font-black tracking-[-0.01em] text-balance uppercase";
const deck = "mt-4 max-w-[62ch] text-entradilla leading-snug font-medium";

function Slip({ pick, past, bankroll, currency }: { pick: PickOfDay; past: boolean; bankroll?: number; currency?: string }) {
  const [home, away] = splitMatch(pick.match);
  const label = betLabel(pick.market, pick.selection, pick.line, { home, away });
  const reasons = (pick.reasons ?? []).filter((r) => !r.startsWith("pick_id="));
  const checkHref = pick.match_id ? evaluarHref(pick.match_id, pick.market, pick.selection, pick.line) : null;
  const registerHref =
    pick.match_id && !past ? evaluarHref(pick.match_id, pick.market, pick.selection, pick.line, pick.odds, pick.bookmaker) : null;
  const figures: { value: string; label: string; tone?: "boli" | "rojo" }[] = [
    ...(pick.prob != null ? [{ value: pct(pick.prob), label: tr("probabilidad", "probability") }] : []),
    ...(pick.fair_odds != null ? [{ value: odds(pick.fair_odds), label: tr("cuota justa", "fair odds") }] : []),
    { value: signedPct(pick.ev), label: tr("valor esperado", "expected value"), tone: pick.ev > 0 ? ("boli" as const) : ("rojo" as const) },
    ...(pick.confidence != null ? [{ value: pct(pick.confidence), label: tr("confianza", "confidence") }] : []),
    ...(pick.stake_pct != null
      ? [
          {
            value: pct(pick.stake_pct, 1),
            label: bankroll
              ? tr(`de la banca, unos ${money(pick.stake_pct * bankroll, currency)}`, `of the bankroll, about ${money(pick.stake_pct * bankroll, currency)}`)
              : tr("de la banca (Kelly fraccionado)", "of the bankroll (fractional Kelly)"),
          },
        ]
      : []),
    ...(past ? [{ value: resultText(pick.result), label: tr("resultado", "result") }] : []),
    ...(past && pick.clv != null ? [{ value: signedPct(pick.clv), label: "CLV" }] : []),
  ];

  return (
    <article aria-labelledby="apuesta-del-dia">
      <h2 id="apuesta-del-dia" className={headline}>
        <span className="sr-only">{tr("Apuesta del día: ", "Bet of the day: ")}</span>
        {registerHref ? (
          <Link
            href={registerHref}
            title={tr("Evaluar y registrar esta apuesta", "Check and record this bet")}
            className="underline decoration-regla decoration-4 underline-offset-8 hover:decoration-tinta"
          >
            {label}
          </Link>
        ) : (
          label
        )}
      </h2>
      <p className={deck}>
        <span className="mr-2 inline-block bg-rojo-portada px-2 align-[0.12em] text-nota leading-6 font-extrabold tracking-[0.08em] text-white uppercase">
          {tr("Apuesta del día", "Bet of the day")}
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
            {tr("El modelo le da un", "The model gives it")} <strong className="num">{pct(pick.prob)}</strong>;{" "}
            {tr("la cuota implica un", "the odds imply")} <strong className="num">{pct(1 / pick.odds)}</strong>.
          </>
        )}
      </p>

      <div className="mt-6 grid grid-cols-2 items-end gap-x-9 gap-y-5 border-t-[3px] border-b border-tinta py-4 sm:flex sm:flex-wrap">
        <div className="col-span-2">
          <p className="cond num text-cuota leading-none font-black">
            <span className="resalte inline-block px-2 pt-1 leading-[0.85]">{odds(pick.odds)}</span>
          </p>
          <p className="mt-2 text-nota leading-snug text-grafito">
            {pick.bookmaker ? tr(`cuota en ${bookmakerName(pick.bookmaker)}`, `odds at ${bookmakerName(pick.bookmaker)}`) : tr("cuota", "odds")}
          </p>
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
      {checkHref && !past && (
        <Link href={checkHref} className="mt-4 inline-flex min-h-10 items-center text-interfaz font-bold text-boli underline underline-offset-4">
          {tr("Comprobar la cuota de Betano", "Check the Betano odds")}
        </Link>
      )}
    </article>
  );
}

function NoPick({ note, past }: { note: string | null; past: boolean }) {
  return (
    <article aria-labelledby="apuesta-del-dia">
      <h2 id="apuesta-del-dia" className={headline}>
        {past ? tr("Ese día no hubo apuesta del día", "There was no bet of the day that day") : tr("Hoy no hay apuesta del día", "No bet of the day today")}
      </h2>
      <p className={deck}>
        {note
          ? note.replace(/^(Hoy no hay apuesta del día|No bet of the day today): /, "").replace(/^./, (c) => c.toUpperCase())
          : tr("Ninguna apuesta superó los umbrales de probabilidad, valor y confianza.", "No bet beat the probability, value and confidence thresholds.")}
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
    { v: n, l: n === 1 ? tr("partido analizado", "match analysed") : tr("partidos analizados", "matches analysed") },
    { v: value, l: value === 1 ? tr("cuota con valor", "value price") : tr("cuotas con valor", "value prices") },
    { v: pass, l: pass === 1 ? tr("pasa el corte", "passes the cut") : tr("pasan el corte", "pass the cut") },
    { v: props, l: tr("props para revisar", "props to check") },
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
          {tr("La jornada", "Fixtures")}
        </h2>
        <span className="text-nota font-semibold text-grafito">{tr("1X2 del modelo, en %", "Model 1X2, in %")}</span>
      </div>
      {rows.length === 0 ? (
        <Empty>{tr("No hay partidos de las nueve competiciones este día.", "No matches from the nine competitions this day.")}</Empty>
      ) : (
        <table className="w-full table-fixed border-collapse text-interfaz">
          <caption className="sr-only">
            {tr("Partidos del día con la probabilidad de local, empate y visitante", "The day's matches with the home, draw and away probability")}
          </caption>
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
                {tr("Hora", "Time")}
              </th>
              <th scope="col" className="pt-1.5 text-left font-semibold">
                <span className="sr-only">{tr("Partido", "Match")}</span>
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
                      {(m.stage === "confirmed" || !!m.alerts?.length || !!m.rivalry) && (
                        <span className="mt-1 flex flex-wrap gap-1">
                          {m.stage === "confirmed" && <Tag tone="confirmada">{stageText(m.stage)}</Tag>}
                          <RivalryTag name={m.rivalry} />
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
          {all ? tr("Mostrar menos", "Show fewer") : tr(`Mostrar los ${rows.length}`, `Show all ${rows.length}`)}
        </button>
      )}
    </section>
  );
}

function MarginNote() {
  return (
    <aside className="border border-regla bg-negro p-5 text-interfaz leading-relaxed text-white/85">
      <h2 className="cond mb-2 text-lateral leading-none font-black text-amarillo uppercase">{tr("Antes de apostar", "Before you bet")}</h2>
      <p>
        {tr(
          <>
            El backtest de 2024-25 y 2025-26 muestra que el modelo <strong className="text-white">no le gana a bet365</strong> en
            1X2, goles ni hándicap asiático. Trata estas apuestas como candidatas para revisar, no como ganancia segura.
          </>,
          <>
            The 2024-25 and 2025-26 backtest shows the model <strong className="text-white">does not beat bet365</strong> in
            1X2, goals or Asian handicap. Treat these bets as candidates to check, not as a sure win.
          </>,
        )}
      </p>
      <p className="mt-2">
        {tr(
          "Donde más margen puede haber es en props: remates, tarjetas según el árbitro y noticias de alineaciones que el mercado aún no recoge.",
          "The biggest margin may be in props: shots, cards depending on the referee and line-up news the market has not priced in yet.",
        )}
      </p>
      <p className="mt-2">
        {tr(
          "La apuesta del día es la de mayor valor por confianza entre las que pasan el corte, que pide 60 % o más de probabilidad. Algunos días no hay ninguna.",
          "The bet of the day is the one with the highest value times confidence among those that pass the cut, which requires a 60% or higher probability. Some days there is none.",
        )}
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
  if (row.status === "withdrawn") return <Tag>{tr("Retirada", "Withdrawn")}</Tag>;
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
    return (
      <Tag tone="boli">
        {short
          ? live
            ? tr("Pasa", "Passes")
            : tr("Pasó", "Passed")
          : live
            ? tr("Pasa el corte", "Passes the cut")
            : tr("Pasó el corte", "Passed the cut")}
      </Tag>
    );
  }
  return (
    <Tag>
      {short
        ? live
          ? tr("No llega", "Short")
          : tr("No llegó", "Fell short")
        : live
          ? tr("No llega al corte", "Short of the cut")
          : tr("No llegó al corte", "Fell short of the cut")}
    </Tag>
  );
}

/** Nombre de la apuesta; si pasa el corte y aún no se juega, lleva a Evaluar para registrarla */
function BetName({ row, home, away }: { row: ValueBet | PastValueBet; home: string; away: string }) {
  const label = betLabel(row.market, row.selection, row.line, { home, away });
  if (!isLive(row) || !row.qualifies) return <>{label}</>;
  return (
    <Link
      href={evaluarHref(row.match_id, row.market, row.selection, row.line, row.odds, row.bookmaker)}
      title={tr("Evaluar y registrar esta apuesta", "Check and record this bet")}
      className={betLink}
    >
      {label}
    </Link>
  );
}

function ValueBets({ rows: input, order }: { rows: (ValueBet | PastValueBet)[]; order: Order }) {
  const [all, setAll] = useState(false);
  // Apuesta con el aviso del radar abierto, por su identidad (el índice cambia al reordenar o mostrar todas)
  const [open, setOpen] = useState<string | null>(null);
  const keyOf = (r: ValueBet | PastValueBet) => `${r.match}|${r.market}|${r.selection}|${r.line}|${"bookmaker" in r ? r.bookmaker : ""}`;
  const toggle = (r: ValueBet | PastValueBet) => setOpen(open === keyOf(r) ? null : keyOf(r));
  if (input.length === 0) return <Empty>{tr("No hay cuotas con valor positivo para este día.", "No positive-value odds for this day.")}</Empty>;
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
              {i === divider && <p className="mb-3 text-nota font-semibold text-grafito">{tr("No llegan al corte", "Short of the cut")}</p>}
              <div className="flex items-start justify-between gap-4">
                <span className="font-semibold">
                  <BetName row={r} home={home} away={away} />
                </span>
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
                {isLive(r) && tr(`, en ${bookmakerName(r.bookmaker)}`, `, at ${bookmakerName(r.bookmaker)}`)}
              </p>
              {isLive(r) && r.rivalry && (
                <span className="mt-1 flex">
                  <RivalryTag name={r.rivalry} />
                </span>
              )}
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
                  {tr("Valor", "Value")} <strong className={`num ${r.ev > 0 ? "text-boli" : "text-rojo"}`}>{signedPct(r.ev)}</strong>
                </span>
                {r.confidence != null && (
                  <span>
                    {tr("Confianza", "Confidence")} <strong className="num">{pct(r.confidence)}</strong>
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
              <th className={th}>{tr("Partido", "Match")}</th>
              <th className={th}>{tr("Apuesta", "Bet")}</th>
              <th className={`${th} text-right`}>{tr("Cuota", "Odds")}</th>
              {live && <th className={`${th} w-40`}>{tr("Margen", "Margin")}</th>}
              <th className={`${th} text-right`}>Prob.</th>
              <th className={`${th} text-right`}>{tr("Valor", "Value")}</th>
              <th className={`${th} text-right`}>{tr("Confianza", "Confidence")}</th>
              {!live && <th className={th}>{tr("Resultado", "Result")}</th>}
              <th className={th}>{tr("Corte", "Cut")}</th>
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
                        {tr("No llegan al corte", "Short of the cut")}
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
                      {isLive(r) && r.rivalry && (
                        <span className="mt-1 flex">
                          <RivalryTag name={r.rivalry} />
                        </span>
                      )}
                      {isLive(r) && <AlertTags alerts={r.alerts} open={open === keyOf(r)} onToggle={() => toggle(r)} />}
                    </td>
                    <td className={td}>
                      <BetName row={r} home={home} away={away} />
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
          {all ? tr("Mostrar menos", "Show fewer") : tr(`Mostrar las ${rows.length}`, `Show all ${rows.length}`)}
        </button>
      )}
    </>
  );
}

function Props({ rows }: { rows: PropMinOdds[] }) {
  const [all, setAll] = useState(false);
  if (rows.length === 0) return <Empty>{tr("No hay props que revisar para este día.", "No props to check for this day.")}</Empty>;
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
                <UnusualTag recent={r.recent_starts} />
                <p className="mt-0.5 text-nota text-grafito">
                  {tr(
                    `${r.match}. Probabilidad ${pct(r.prob)}, cuota justa ${odds(r.fair_odds)}`,
                    `${r.match}. Probability ${pct(r.prob)}, fair odds ${odds(r.fair_odds)}`,
                  )}
                </p>
              </div>
              <div className="shrink-0 text-right">
                <p className="cond num text-2xl leading-none font-bold text-boli">{odds(r.min_odds)}</p>
                <p className="text-etiqueta text-grafito">{tr("mínima", "minimum")}</p>
              </div>
            </li>
          );
        })}
      </ul>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[640px] border-collapse text-interfaz">
          <thead className="border-b border-tinta">
            <tr>
              <th className={th}>{tr("Partido", "Match")}</th>
              <th className={th}>{tr("Apuesta", "Bet")}</th>
              <th className={`${th} text-right`}>{tr("Probabilidad", "Probability")}</th>
              <th className={`${th} text-right`}>{tr("Cuota justa", "Fair odds")}</th>
              <th className={`${th} text-right`}>{tr("Cuota mínima", "Minimum odds")}</th>
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
                  <td className={td}>
                    {betLabel(r.market, r.selection, r.line, { home, away, player: r.player })}
                    {r.recent_starts != null && (
                      <span className="ml-1.5">
                        <UnusualTag recent={r.recent_starts} />
                      </span>
                    )}
                  </td>
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
          {all ? tr("Mostrar menos", "Show fewer") : tr(`Mostrar las ${rows.length}`, `Show all ${rows.length}`)}
        </button>
      )}
    </>
  );
}
