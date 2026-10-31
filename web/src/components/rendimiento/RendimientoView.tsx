"use client";

import type { EChartsCoreOption } from "echarts/core";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { type FormEvent, Fragment, useMemo, useState } from "react";
import { PorQueFallo } from "@/components/PorQueFallo";
import { baseOption, Chart, type ChartTheme, useChartTheme } from "@/components/Chart";
import { PickRecord } from "@/components/PickRecord";
import { Button, Empty, ErrorNote, Figure, Loading, PageTitle, Section, Tag } from "@/components/ui";
import { put, useApi } from "@/lib/api";
import {
  competitionName,
  int,
  money,
  odds,
  pct,
  RESULT_TONE,
  resultText,
  shortDate,
  signedPct,
  splitMatch,
} from "@/lib/format";
import { tr } from "@/lib/i18n";
import { betLabel, bookmakerName, clvRefText, marketName } from "@/lib/markets";
import type { Aggregate, Bankroll, Performance, PickHistory, QualifiedPicks, UserBet } from "@/lib/types";

const periods = () => [
  { value: "", label: tr("Todo", "All") },
  { value: "7", label: tr("7 días", "7 days") },
  { value: "30", label: tr("30 días", "30 days") },
  { value: "90", label: tr("90 días", "90 days") },
];

export function RendimientoView() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const days = params.get("periodo") ?? "";
  const perf = useApi<Performance>(`/performance${days ? `?days=${days}` : ""}`);
  const bets = useApi<UserBet[]>("/bets");
  const history = useApi<PickHistory>("/picks/history?days=365");

  function setDays(v: string) {
    const next = new URLSearchParams(params.toString());
    if (v) next.set("periodo", v);
    else next.delete("periodo");
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  }

  const p = perf.data;
  const currency = p?.bankroll.currency ?? "PEN";

  return (
    <>
      <PageTitle
        title={tr("Mis apuestas", "My bets")}
        sub={tr(
          "Tu rendimiento real con las apuestas que registras. Se liquidan solas cuando termina el partido.",
          "Your real performance with the bets you record. They settle on their own when the match ends.",
        )}
        actions={
          <fieldset className="flex flex-wrap gap-1">
            <legend className="sr-only">{tr("Periodo", "Period")}</legend>
            {periods().map((o) => (
              <button
                key={o.value}
                type="button"
                aria-pressed={days === o.value}
                onClick={() => setDays(o.value)}
                className={`h-9 border px-3 text-interfaz font-semibold ${
                  days === o.value ? "border-tinta bg-tinta text-papel" : "border-regla bg-hoja text-grafito hover:text-tinta"
                }`}
              >
                {o.label}
              </button>
            ))}
          </fieldset>
        }
      />

      {perf.error ? (
        <div className="pb-10">
          <ErrorNote error={perf.error} onRetry={() => perf.mutate()} />
        </div>
      ) : !p ? (
        <div className="pb-10">
          <Loading lines={4} />
        </div>
      ) : (
        <>
          <Resumen total={p.total} currency={currency} />
          <Banca b={p.bankroll} onSaved={() => perf.mutate()} />
          <Evolucion bets={bets.data} currency={currency} />
          <Desglose p={p} currency={currency} />
        </>
      )}

      <Section title={tr("Últimas apuestas registradas", "Latest recorded bets")}>
        {bets.error ? (
          <ErrorNote error={bets.error} onRetry={() => bets.mutate()} />
        ) : !bets.data ? (
          <Loading lines={3} />
        ) : bets.data.length === 0 ? (
          <Empty>
            {tr("Aún no registras ninguna apuesta. Cuando hagas una, regístrala desde", "You have not recorded any bets yet. When you place one, record it from")}{" "}
            <Link href="/evaluar" className="font-semibold text-boli underline underline-offset-4">
              {tr("Evaluar cuota", "Check odds")}
            </Link>{" "}
            {tr("para seguir tu ROI y tu CLV.", "to track your ROI and CLV.")}
          </Empty>
        ) : (
          <BetsTable rows={bets.data} currency={currency} />
        )}
      </Section>

      <Section
        title={tr("La apuesta del día del sistema", "The system's bet of the day")}
        intro={tr(
          "Cómo le fue a la apuesta del día, con 1 unidad por apuesta. Mide al sistema, no a ti: sirve para decidir cuánto confiar en él.",
          "How the bet of the day did, staking 1 unit per bet. It measures the system, not you: it helps you decide how much to trust it.",
        )}
      >
        <PickRecord variant="row" />
        <h3 className="semi mb-3 text-base font-bold">{tr("Último año", "Last year")}</h3>
        {history.error ? (
          <ErrorNote error={history.error} onRetry={() => history.mutate()} />
        ) : !history.data ? (
          <Loading lines={3} />
        ) : (
          <Historial h={history.data} />
        )}
      </Section>

      <Section
        id="corte"
        title={tr("Las que pasan el corte", "Bets that pass the cut")}
        intro={tr(
          "Todas las apuestas con valor que pasaron el corte de valor, probabilidad y confianza, no solo la apuesta del día. Se guarda el último cálculo antes del partido: las que se retiraron o dejaron de pasar el corte no cuentan. Con 1 unidad por apuesta. El CLV compara la cuota tomada con la justa (sin margen) de Pinnacle unos 15 minutos antes del partido, o con el cierre de bet365: con unos cientos de apuestas dice si hay ventaja mucho antes que el ROI. Hasta el 28-10 la de Pinnacle solía ser de horas antes.",
          "Every value bet that passed the value, probability and confidence cut, not just the bet of the day. The last calculation before kick-off is kept: those withdrawn or that stopped passing the cut do not count. Staking 1 unit per bet. CLV compares the odds taken with Pinnacle's fair (margin-free) odds about 15 minutes before kick-off, or with the bet365 closing line: with a few hundred bets it shows whether there is an edge long before ROI does. Until 28-10 the Pinnacle price was usually from hours before.",
        )}
      >
        <PickRecord variant="row" source="corte" />
        <CorteHistorial />
      </Section>
    </>
  );
}

// --------------------------------------------------------------------------- resumen y banca

function Resumen({ total, currency }: { total: Aggregate; currency: string }) {
  const tone = (x: number | null) => (x == null || x === 0 ? undefined : x > 0 ? "boli" : "rojo");
  return (
    <Section
      title={tr("Resumen", "Summary")}
      intro={tr(
        "El CLV compara tu cuota con la de cierre. Un CLV positivo y sostenido es la mejor señal de que apuestas con criterio, aunque el resultado tarde en reflejarlo.",
        "CLV compares your odds with the closing odds. A positive, sustained CLV is the best sign that you bet with judgement, even if results take time to show it.",
      )}
    >
      {total.bets === 0 ? (
        <Empty>{tr("Sin apuestas liquidadas en este periodo.", "No settled bets in this period.")}</Empty>
      ) : (
        <div className="grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-4 lg:grid-cols-7">
          <Figure size="lg" value={money(total.profit, currency, true)} label={tr("beneficio", "profit")} tone={tone(total.profit)} />
          <Figure size="lg" value={signedPct(total.roi)} label="ROI" tone={tone(total.roi)} />
          <Figure size="lg" value={signedPct(total.avg_clv)} label={tr("CLV medio", "average CLV")} tone={tone(total.avg_clv)} />
          <Figure value={pct(total.hit_rate)} label={tr("acierto", "hit rate")} />
          <Figure value={int(total.bets)} label={tr("apuestas liquidadas", "settled bets")} />
          <Figure value={money(total.staked, currency)} label={tr("apostado", "staked")} />
          <Figure value={odds(total.avg_odds)} label={tr("cuota media", "average odds")} />
        </div>
      )}
    </Section>
  );
}

function LossMeter({ label, profit, limit, currency }: { label: string; profit: number; limit: number; currency: string }) {
  // El límite es una pérdida (número negativo). Se muestra qué parte ya se consumió.
  const used = limit < 0 ? Math.min(1, Math.max(0, -profit / -limit)) : 0;
  const tone = used >= 1 ? "bg-rojo" : used >= 0.6 ? "bg-tarjeta" : "bg-tinta";
  return (
    <div>
      <div className="flex items-baseline justify-between gap-4">
        <span className="font-semibold">{label}</span>
        <span className={`cond num text-lateral font-bold ${profit > 0 ? "text-boli" : profit < 0 ? "text-rojo" : ""}`}>
          {money(profit, currency, true)}
        </span>
      </div>
      <div
        className="mt-1.5 h-2 rounded-full bg-regla-suave"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(used * 100)}
        aria-label={tr(`${label}: ${pct(used)} del límite de pérdida usado`, `${label}: ${pct(used)} of the loss limit used`)}
      >
        <div className={`h-2 rounded-full ${tone}`} style={{ width: `${used * 100}%` }} />
      </div>
      <p className="mt-1 text-nota text-grafito">
        {profit >= 0
          ? tr(`Sin pérdidas. Límite de pérdida: ${money(-limit, currency)}`, `No losses. Loss limit: ${money(-limit, currency)}`)
          : tr(`Usado el ${pct(used)} del límite de pérdida de ${money(-limit, currency)}`, `${pct(used)} of the ${money(-limit, currency)} loss limit used`)}
      </p>
    </div>
  );
}

function Banca({ b, onSaved }: { b: Bankroll; onSaved: () => void }) {
  const [editing, setEditing] = useState(false);
  const tone = b.total_profit > 0 ? "boli" : b.total_profit < 0 ? "rojo" : undefined;
  return (
    <Section
      title={tr("Banca", "Bankroll")}
      intro={tr(
        "La banca inicial es el dinero con el que empiezas: de ella salen el stake sugerido y los límites de pérdida diaria y semanal. Al llegar a un límite, para.",
        "The starting bankroll is the money you begin with: the suggested stake and the daily and weekly loss limits come from it. When you hit a limit, stop.",
      )}
    >
      <div className="grid gap-x-10 gap-y-6 md:grid-cols-[auto_minmax(0,1fr)_minmax(0,1fr)]">
        <div className="grid grid-cols-2 gap-x-8 gap-y-4 md:grid-cols-1">
          {editing ? (
            <BancaForm
              b={b}
              onDone={(saved) => {
                setEditing(false);
                if (saved) onSaved();
              }}
            />
          ) : (
            <div>
              <Figure size="lg" value={money(b.bankroll, b.currency)} label={tr("banca inicial", "starting bankroll")} />
              <button
                type="button"
                onClick={() => setEditing(true)}
                className="inline-flex min-h-10 items-center text-interfaz font-semibold text-boli underline underline-offset-4"
              >
                {tr("Editar banca inicial", "Edit starting bankroll")}
              </button>
            </div>
          )}
          <Figure
            value={money(b.current, b.currency)}
            label={tr(
              `banca actual (${money(b.total_profit, b.currency, true)} desde el inicio)`,
              `current bankroll (${money(b.total_profit, b.currency, true)} since the start)`,
            )}
            tone={tone}
          />
          <Figure
            value={int(b.pending_bets)}
            label={tr(
              `pendientes de liquidar, ${money(b.pending_stake, b.currency)} en juego`,
              `waiting to settle, ${money(b.pending_stake, b.currency)} at stake`,
            )}
          />
        </div>
        <LossMeter label={tr("Hoy", "Today")} profit={b.day_profit} limit={b.daily_loss_limit} currency={b.currency} />
        <LossMeter label={tr("Esta semana", "This week")} profit={b.week_profit} limit={b.weekly_loss_limit} currency={b.currency} />
      </div>
      {b.warnings.map((w) => (
        <p key={w} role="alert" className="mt-4 border-t-[3px] border-rojo bg-rojo-suave px-3 py-2 font-semibold">
          {w}
        </p>
      ))}
    </Section>
  );
}

const currencies = () => [
  ["PEN", tr("Soles (S/)", "Soles (S/)")],
  ["USD", tr("Dólares (US$)", "Dollars (US$)")],
  ["EUR", tr("Euros (€)", "Euros (€)")],
];

function BancaForm({ b, onDone }: { b: Bankroll; onDone: (saved: boolean) => void }) {
  const [amount, setAmount] = useState(String(b.bankroll));
  const [currency, setCurrency] = useState(b.currency);
  const [state, setState] = useState<{ busy: boolean; error?: string }>({ busy: false });

  async function save(e: FormEvent) {
    e.preventDefault();
    const value = Number(amount.replace(",", "."));
    if (!Number.isFinite(value) || value <= 0) {
      setState({ busy: false, error: tr("Escribe un monto mayor que 0.", "Type an amount greater than 0.") });
      return;
    }
    setState({ busy: true });
    try {
      await put("/bankroll", { bankroll: value, currency });
      onDone(true);
    } catch (err) {
      setState({ busy: false, error: (err as Error).message });
    }
  }

  return (
    <form onSubmit={save} className="max-w-xs space-y-3" aria-label={tr("Editar banca inicial", "Edit starting bankroll")}>
      <div>
        <label htmlFor="banca-monto" className="mb-1 block text-nota font-semibold">
          {tr("Banca inicial", "Starting bankroll")}
        </label>
        <div className="flex gap-2">
          <input
            id="banca-monto"
            type="text"
            inputMode="decimal"
            autoComplete="off"
            autoFocus
            value={amount}
            onChange={(e) => {
              setAmount(e.target.value);
              setState({ busy: false });
            }}
            aria-invalid={!!state.error}
            aria-describedby={state.error ? "banca-error" : undefined}
            className="num h-10 min-w-0 flex-1 border border-regla bg-hoja px-3 text-tinta focus:border-boli"
          />
          <label htmlFor="banca-moneda" className="sr-only">
            {tr("Moneda", "Currency")}
          </label>
          <select
            id="banca-moneda"
            value={currency}
            onChange={(e) => setCurrency(e.target.value)}
            className="h-10 border border-regla bg-hoja px-2 text-tinta focus:border-boli"
          >
            {currencies().map(([code, name]) => (
              <option key={code} value={code}>
                {name}
              </option>
            ))}
          </select>
        </div>
        {state.error && (
          <p id="banca-error" role="alert" className="mt-1 text-nota text-rojo">
            {state.error}
          </p>
        )}
      </div>
      <div className="flex gap-2">
        <Button type="submit" variant="primary" disabled={state.busy}>
          {state.busy ? tr("Guardando…", "Saving…") : tr("Guardar", "Save")}
        </Button>
        <Button onClick={() => onDone(false)} disabled={state.busy}>
          {tr("Cancelar", "Cancel")}
        </Button>
      </div>
    </form>
  );
}

// --------------------------------------------------------------------------- gráficas

function cumulativeOption(t: ChartTheme, values: number[], currency: string): EChartsCoreOption {
  const fmt = (v: number) => money(v, currency, true);
  return {
    ...baseOption(t),
    grid: { left: 8, right: 16, top: 16, bottom: 28, containLabel: true },
    tooltip: { ...(baseOption(t).tooltip as object), trigger: "axis", valueFormatter: fmt },
    xAxis: {
      type: "category",
      data: values.map((_, i) => String(i + 1)),
      name: tr("Apuesta n.º", "Bet no."),
      nameLocation: "middle",
      nameGap: 26,
      axisTick: { show: false },
      axisLine: { lineStyle: { color: t.regla } },
      axisLabel: { color: t.grafito },
    },
    yAxis: {
      type: "value",
      axisLabel: { color: t.grafito, formatter: fmt },
      splitLine: { lineStyle: { color: t.reglaSuave } },
    },
    series: [
      {
        type: "line",
        name: tr("Beneficio acumulado", "Cumulative profit"),
        data: values,
        symbol: "circle",
        symbolSize: 5,
        lineStyle: { color: t.tinta, width: 2 },
        itemStyle: { color: t.tinta },
        markLine: {
          silent: true,
          symbol: "none",
          label: { show: false },
          lineStyle: { color: t.grafito, type: "dashed", width: 1 },
          data: [{ yAxis: 0 }],
        },
      },
    ],
  };
}

function roiOption(t: ChartTheme, rows: { name: string; roi: number }[]): EChartsCoreOption {
  const data = [...rows].reverse();
  return {
    ...baseOption(t),
    grid: { left: 8, right: 56, top: 4, bottom: 4, containLabel: true },
    tooltip: { ...(baseOption(t).tooltip as object), trigger: "axis", axisPointer: { type: "none" }, valueFormatter: (v: number) => signedPct(v) },
    xAxis: { type: "value", show: false },
    yAxis: {
      type: "category",
      data: data.map((r) => r.name),
      axisTick: { show: false },
      axisLine: { show: false },
      axisLabel: { color: t.tinta },
    },
    series: [
      {
        type: "bar",
        name: "ROI",
        data: data.map((r) => ({ value: r.roi, itemStyle: { color: r.roi >= 0 ? t.boli : t.rojo } })),
        barWidth: "56%",
        label: { show: true, position: "right", color: t.grafito, formatter: (p: { value: number }) => signedPct(p.value) },
        markLine: {
          silent: true,
          symbol: "none",
          label: { show: false },
          lineStyle: { color: t.grafito, width: 1 },
          data: [{ xAxis: 0 }],
        },
      },
    ],
  };
}

function Evolucion({ bets, currency }: { bets: UserBet[] | undefined; currency: string }) {
  const t = useChartTheme();
  const values = useMemo(() => {
    const settled = (bets ?? []).filter((b) => b.profit != null).sort((a, b) => a.bet_id - b.bet_id);
    return settled.reduce<number[]>((acc, b) => {
      const prev = acc.length ? acc[acc.length - 1] : 0;
      return [...acc, Math.round((prev + (b.profit ?? 0)) * 100) / 100];
    }, []);
  }, [bets]);
  const option = useMemo(() => (t && values.length > 1 ? cumulativeOption(t, values, currency) : null), [t, values, currency]);
  if (!bets) return null;
  return (
    <Section
      title={tr("Beneficio acumulado", "Cumulative profit")}
      intro={tr("Con tus últimas 30 apuestas registradas, en el orden en que las hiciste.", "With your last 30 recorded bets, in the order you placed them.")}
    >
      {values.length < 2 ? (
        <Empty>{tr("Hacen falta al menos dos apuestas liquidadas para dibujar la evolución.", "It takes at least two settled bets to draw the trend.")}</Empty>
      ) : (
        <Chart option={option} height={260} label={tr("Beneficio acumulado apuesta a apuesta", "Cumulative profit bet by bet")} />
      )}
    </Section>
  );
}

// --------------------------------------------------------------------------- desglose

function Desglose({ p, currency }: { p: Performance; currency: string }) {
  if (p.total.bets === 0) return null;
  return (
    <Section
      title={tr("Desglose", "Breakdown")}
      intro={tr(
        "Dónde ganas y dónde pierdes. Con pocas apuestas por grupo, el ROI es sobre todo ruido.",
        "Where you win and where you lose. With few bets per group, ROI is mostly noise.",
      )}
    >
      <div className="grid gap-x-10 gap-y-10 lg:grid-cols-2">
        <Grupo title={tr("Por mercado", "By market")} data={p.market} name={marketLabel} currency={currency} chart />
        <Grupo title={tr("Por competición", "By competition")} data={p.competition} name={competitionName} currency={currency} chart />
        <Grupo title={tr("Por casa", "By bookmaker")} data={p.bookmaker} name={bookmakerName} currency={currency} />
        <Grupo title={tr("Por rango de cuota", "By odds range")} data={p.odds_band} name={oddsBand} currency={currency} />
      </div>
    </Section>
  );
}

const marketLabel = (k: string) => marketName(k);
const oddsBand = (k: string) => k;

function Grupo({
  title,
  data,
  name,
  currency,
  chart = false,
}: {
  title: string;
  data: Record<string, Aggregate>;
  name: (k: string) => string;
  currency: string;
  chart?: boolean;
}) {
  const t = useChartTheme();
  const rows = useMemo(
    () =>
      Object.entries(data)
        .map(([k, a]) => ({ key: k, name: name(k), ...a }))
        .sort((x, y) => y.bets - x.bets),
    [data, name],
  );
  const option = useMemo(
    () =>
      t && chart
        ? roiOption(
            t,
            rows.filter((r) => r.roi != null).map((r) => ({ name: r.name, roi: r.roi as number })),
          )
        : null,
    [t, chart, rows],
  );
  return (
    <div className="min-w-0">
      <h3 className="semi mb-2 font-bold">{title}</h3>
      {chart && rows.length > 0 && <Chart option={option} height={Math.max(80, rows.length * 34)} label={`ROI ${title.toLowerCase()}`} />}
      <div className="overflow-x-auto">
        <table className="w-full min-w-[460px] border-collapse text-nota">
          <thead>
            <tr className="border-b border-regla text-right text-nota text-grafito">
              <th className="py-1.5 pr-3 text-left font-medium">{tr("Grupo", "Group")}</th>
              <th className="py-1.5 pr-3 font-medium">{tr("Apuestas", "Bets")}</th>
              <th className="py-1.5 pr-3 font-medium">{tr("Beneficio", "Profit")}</th>
              <th className="py-1.5 pr-3 font-medium">ROI</th>
              <th className="py-1.5 pr-3 font-medium">{tr("Acierto", "Hit rate")}</th>
              <th className="py-1.5 font-medium">CLV</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((r) => (
              <tr key={r.key} className="num border-b border-regla-suave text-right">
                <td className="py-1.5 pr-3 text-left">{r.name}</td>
                <td className="py-1.5 pr-3">{r.bets}</td>
                <td className={`py-1.5 pr-3 ${r.profit > 0 ? "text-boli" : r.profit < 0 ? "text-rojo" : ""}`}>
                  {money(r.profit, currency, true)}
                </td>
                <td className="py-1.5 pr-3">{signedPct(r.roi)}</td>
                <td className="py-1.5 pr-3">{pct(r.hit_rate)}</td>
                <td className="py-1.5">{signedPct(r.avg_clv)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- tablas

function profitClass(x: number | null | undefined): string {
  return x != null && x > 0 ? "text-boli" : x != null && x < 0 ? "text-rojo" : "";
}

/** Lo apostado: una selección, o las de una combinada con el resultado de cada una */
function BetText({ b }: { b: UserBet }) {
  if (b.market !== "combo" || !b.legs) {
    const [home, away] = splitMatch(b.match);
    return <>{betLabel(b.market, b.selection, b.line, { home, away })}</>;
  }
  return (
    <ul className="space-y-0.5">
      {b.legs.map((lg, i) => {
        const [home, away] = splitMatch(lg.match);
        return (
          <li key={i} className="text-nota">
            <span className="text-grafito">{lg.match}: </span>
            {betLabel(lg.market, lg.selection, lg.line, { home, away, player: lg.player })}
            {lg.odds != null && <span className="num ml-1 text-grafito">({odds(lg.odds)})</span>}
            {lg.result && (
              <span className="ml-2">
                <Tag tone={RESULT_TONE[lg.result] ?? "neutral"}>{resultText(lg.result)}</Tag>
              </span>
            )}
          </li>
        );
      })}
    </ul>
  );
}

function BetsTable({ rows, currency }: { rows: UserBet[]; currency: string }) {
  return (
    <>
      <ul className="divide-y divide-regla-suave border-y border-regla-suave md:hidden">
        {rows.map((b) => {
          return (
            <li key={b.bet_id} className="py-3">
              <div className="flex items-start justify-between gap-4">
                <span className="font-semibold">
                  <BetText b={b} />
                </span>
                <span className="cond num text-2xl leading-none font-bold">{odds(b.odds)}</span>
              </div>
              <p className="mt-0.5 text-nota text-grafito">
                {tr(`${b.match}, en ${bookmakerName(b.bookmaker)}`, `${b.match}, at ${bookmakerName(b.bookmaker)}`)}
              </p>
              <p className="num mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-nota">
                <Tag tone={b.result ? RESULT_TONE[b.result] ?? "neutral" : "tarjeta"}>{resultText(b.result)}</Tag>
                <span>{money(b.stake, currency)}</span>
                {b.profit != null && <strong className={profitClass(b.profit)}>{money(b.profit, currency, true)}</strong>}
                {b.clv != null && <span className="text-grafito">CLV {signedPct(b.clv)}</span>}
              </p>
            </li>
          );
        })}
      </ul>
      <BetsWide rows={rows} currency={currency} />
    </>
  );
}

function BetsWide({ rows, currency }: { rows: UserBet[]; currency: string }) {
  return (
    <div className="hidden overflow-x-auto md:block">
      <table className="w-full min-w-[760px] border-collapse text-interfaz">
        <thead>
          <tr className="border-b border-regla text-left text-nota text-grafito">
            <th className="py-2 pr-4 font-medium">{tr("Partido", "Match")}</th>
            <th className="py-2 pr-4 font-medium">{tr("Apuesta", "Bet")}</th>
            <th className="py-2 pr-4 text-right font-medium">{tr("Cuota", "Odds")}</th>
            <th className="py-2 pr-4 text-right font-medium">{tr("Importe", "Stake")}</th>
            <th className="py-2 pr-4 font-medium">{tr("Resultado", "Result")}</th>
            <th className="py-2 pr-4 text-right font-medium">{tr("Beneficio", "Profit")}</th>
            <th className="py-2 text-right font-medium">CLV</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((b) => {
            return (
              <tr key={b.bet_id} className="border-b border-regla-suave align-top">
                <td className="py-2 pr-4">{b.match}</td>
                <td className="py-2 pr-4">
                  <BetText b={b} />
                  <span className="block text-nota text-grafito">{bookmakerName(b.bookmaker)}</span>
                </td>
                <td className="cond num py-2 pr-4 text-right text-lg font-bold">{odds(b.odds)}</td>
                <td className="num py-2 pr-4 text-right">{money(b.stake, currency)}</td>
                <td className="py-2 pr-4">
                  <Tag tone={b.result ? RESULT_TONE[b.result] ?? "neutral" : "tarjeta"}>{resultText(b.result)}</Tag>
                </td>
                <td className={`num py-2 pr-4 text-right ${profitClass(b.profit)}`}>
                  {b.profit != null ? money(b.profit, currency, true) : "—"}
                </td>
                <td className="num py-2 text-right">{signedPct(b.clv)}</td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

/** Las que pasaron el corte en los últimos 60 días, de la más reciente a la más antigua, con su resultado */
function CorteHistorial() {
  const { data, error, mutate } = useApi<QualifiedPicks>("/picks/qualified");
  const [all, setAll] = useState(false);
  if (error) return <ErrorNote error={error} onRetry={() => mutate()} />;
  if (!data) return <Loading lines={3} />;
  if (data.picks.length === 0) {
    return (
      <Empty>
        {tr(
          "Aún no hay apuestas que pasen el corte. Se guardan solas cada día y, cuando termina el partido, se anota si se ganaron o se perdieron.",
          "No bets have passed the cut yet. They are saved on their own every day and, when the match ends, marked as won or lost.",
        )}
      </Empty>
    );
  }
  const shown = all ? data.picks : data.picks.slice(0, 12);
  const tag = (r: QualifiedPicks["picks"][number]) => (
    <Tag tone={r.result ? (RESULT_TONE[r.result] ?? "neutral") : "tarjeta"}>
      {r.result ? resultText(r.result) : tr("Por jugarse", "To be played")}
    </Tag>
  );
  return (
    <>
      <h3 className="semi mb-3 text-base font-bold">{tr("Últimos 60 días", "Last 60 days")}</h3>
      <ul className="divide-y divide-regla-suave border-y border-regla-suave md:hidden">
        {shown.map((r) => {
          const [home, away] = splitMatch(r.match);
          return (
            <li key={r.pick_id} className="py-3">
              <div className="flex items-start justify-between gap-4">
                <span className="font-semibold">{betLabel(r.market, r.selection, r.line, { home, away })}</span>
                <span className="cond num text-2xl leading-none font-bold">{odds(r.odds)}</span>
              </div>
              <p className="mt-0.5 text-nota text-grafito">
                {shortDate(r.date)}, {tr(`${r.match}, en ${bookmakerName(r.bookmaker)}`, `${r.match}, at ${bookmakerName(r.bookmaker)}`)}
              </p>
              <p className="num mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-nota">
                {tag(r)}
                <span>
                  {tr("Valor", "Value")} <strong className="text-boli">{signedPct(r.ev)}</strong>
                </span>
                {r.profit_units != null && (
                  <span className={profitClass(r.profit_units)}>
                    {r.profit_units > 0 ? "+" : ""}
                    {r.profit_units.toFixed(2)} u
                  </span>
                )}
                {r.clv != null && (
                  <span className={profitClass(r.clv)}>
                    CLV {signedPct(r.clv)} <span className="text-grafito">({clvRefText(r.clv_ref)})</span>
                  </span>
                )}
                {r.is_pick_of_day && <Tag tone="boli">{tr("Apuesta del día", "Bet of the day")}</Tag>}
              </p>
              {r.clv_note && <p className="mt-1 text-nota text-grafito">{r.clv_note}</p>}
            </li>
          );
        })}
      </ul>
      <div className="hidden overflow-x-auto md:block">
        <table className="w-full min-w-[820px] border-collapse text-interfaz">
          <thead>
            <tr className="border-b border-regla text-left text-nota text-grafito">
              <th className="py-2 pr-4 font-medium">{tr("Fecha", "Date")}</th>
              <th className="py-2 pr-4 font-medium">{tr("Partido", "Match")}</th>
              <th className="py-2 pr-4 font-medium">{tr("Apuesta", "Bet")}</th>
              <th className="py-2 pr-4 text-right font-medium">{tr("Cuota", "Odds")}</th>
              <th className="py-2 pr-4 text-right font-medium">{tr("Valor", "Value")}</th>
              <th className="py-2 pr-4 text-right font-medium">CLV</th>
              <th className="py-2 pr-4 font-medium">{tr("Resultado", "Result")}</th>
              <th className="py-2 text-right font-medium">{tr("Unidades", "Units")}</th>
            </tr>
          </thead>
          <tbody>
            {shown.map((r) => {
              const [home, away] = splitMatch(r.match);
              return (
                <tr key={r.pick_id} className="border-b border-regla-suave">
                  <td className="num py-2 pr-4">{shortDate(r.date)}</td>
                  <td className="py-2 pr-4">{r.match}</td>
                  <td className="py-2 pr-4">
                    {betLabel(r.market, r.selection, r.line, { home, away })}
                    <span className="block text-nota text-grafito">
                      {bookmakerName(r.bookmaker)}
                      {r.is_pick_of_day && tr(", apuesta del día", ", bet of the day")}
                    </span>
                  </td>
                  <td className="cond num py-2 pr-4 text-right text-lg font-bold">{odds(r.odds)}</td>
                  <td className="num py-2 pr-4 text-right font-semibold text-boli">{signedPct(r.ev)}</td>
                  <td className="py-2 pr-4 text-right">
                    <span className={`num font-semibold ${profitClass(r.clv)}`}>{signedPct(r.clv)}</span>
                    {(r.clv_ref || r.clv_note) && (
                      <span className="block text-nota text-grafito">
                        {r.clv_ref ? clvRefText(r.clv_ref) : tr("sin referencia", "no reference")}
                      </span>
                    )}
                  </td>
                  <td className="py-2 pr-4">{tag(r)}</td>
                  <td className={`num py-2 text-right font-semibold ${profitClass(r.profit_units)}`}>
                    {r.profit_units == null ? "—" : `${r.profit_units > 0 ? "+" : ""}${r.profit_units.toFixed(2)} u`}
                  </td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
      {data.picks.length > 12 && (
        <button
          type="button"
          onClick={() => setAll(!all)}
          className="mt-1 inline-flex min-h-10 items-center text-interfaz font-semibold text-boli underline underline-offset-4"
        >
          {all ? tr("Mostrar menos", "Show fewer") : tr(`Mostrar las ${data.picks.length}`, `Show all ${data.picks.length}`)}
        </button>
      )}
    </>
  );
}

const LOST = new Set(["loss", "half_loss"]);

/** «Por qué falló»: botón en las perdidas que abre el análisis debajo de la fila */
function WhyButton({ open, onToggle }: { open: boolean; onToggle: () => void }) {
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      className="ml-3 inline-flex min-h-6 items-center text-nota font-bold text-boli underline underline-offset-2"
    >
      {open ? tr("Ocultar", "Hide") : tr("Por qué falló", "Why it lost")}
    </button>
  );
}

function Historial({ h }: { h: PickHistory }) {
  const [open, setOpen] = useState<number | null>(null);
  const toggle = (id: number) => setOpen(open === id ? null : id);
  if (h.picks === 0) {
    return (
      <Empty>
        {tr(
          "Aún no hay apuestas del día liquidadas. El historial empieza a llenarse a medida que el sistema elige una y el partido termina.",
          "No bet of the day has settled yet. The history fills up as the system picks one and the match ends.",
        )}
      </Empty>
    );
  }
  return (
    <>
      <div className="grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-5">
        <Figure value={int(h.picks)} label={tr("apuestas del día", "bets of the day")} />
        <Figure
          value={`${h.profit_units > 0 ? "+" : ""}${h.profit_units.toFixed(2)} u`}
          label={tr("beneficio en unidades", "profit in units")}
          tone={h.profit_units > 0 ? "boli" : h.profit_units < 0 ? "rojo" : undefined}
        />
        <Figure value={signedPct(h.roi)} label="ROI" />
        <Figure value={pct(h.hit_rate)} label={tr("acierto", "hit rate")} />
        <Figure value={signedPct(h.avg_clv)} label={tr("CLV medio", "average CLV")} />
      </div>
      <ul className="mt-6 divide-y divide-regla-suave border-y border-regla-suave md:hidden">
        {[...h.last].reverse().map((r, i) => {
          const [home, away] = splitMatch(r.match);
          return (
            <li key={i} className="py-3">
              <div className="flex items-start justify-between gap-4">
                <span className="font-semibold">{betLabel(r.market, r.selection, r.line, { home, away })}</span>
                <span className="cond num text-2xl leading-none font-bold">{odds(r.odds)}</span>
              </div>
              <p className="mt-0.5 text-nota text-grafito">
                {shortDate(r.date)}, {r.match}
              </p>
              <p className="num mt-1.5 flex flex-wrap items-center gap-x-4 text-nota">
                <Tag tone={r.result ? RESULT_TONE[r.result] ?? "neutral" : "tarjeta"}>{resultText(r.result)}</Tag>
                {r.clv != null && <span className="text-grafito">CLV {signedPct(r.clv)}</span>}
                {r.result && LOST.has(r.result) && <WhyButton open={open === r.pick_id} onToggle={() => toggle(r.pick_id)} />}
              </p>
              {open === r.pick_id && <PorQueFallo pickId={r.pick_id} />}
            </li>
          );
        })}
      </ul>
      <div className="mt-6 hidden overflow-x-auto md:block">
        <table className="w-full min-w-[640px] border-collapse text-interfaz">
          <thead>
            <tr className="border-b border-regla text-left text-nota text-grafito">
              <th className="py-2 pr-4 font-medium">{tr("Fecha", "Date")}</th>
              <th className="py-2 pr-4 font-medium">{tr("Partido", "Match")}</th>
              <th className="py-2 pr-4 font-medium">{tr("Apuesta", "Bet")}</th>
              <th className="py-2 pr-4 text-right font-medium">{tr("Cuota", "Odds")}</th>
              <th className="py-2 pr-4 font-medium">{tr("Resultado", "Result")}</th>
              <th className="py-2 text-right font-medium">CLV</th>
            </tr>
          </thead>
          <tbody>
            {[...h.last].reverse().map((r, i) => {
              const [home, away] = splitMatch(r.match);
              return (
                <Fragment key={i}>
                <tr className="border-b border-regla-suave">
                  <td className="num py-2 pr-4">{shortDate(r.date)}</td>
                  <td className="py-2 pr-4">{r.match}</td>
                  <td className="py-2 pr-4">{betLabel(r.market, r.selection, r.line, { home, away })}</td>
                  <td className="cond num py-2 pr-4 text-right text-lg font-bold">{odds(r.odds)}</td>
                  <td className="py-2 pr-4">
                    <Tag tone={r.result ? RESULT_TONE[r.result] ?? "neutral" : "tarjeta"}>{resultText(r.result)}</Tag>
                    {r.result && LOST.has(r.result) && <WhyButton open={open === r.pick_id} onToggle={() => toggle(r.pick_id)} />}
                  </td>
                  <td className="num py-2 text-right">{signedPct(r.clv)}</td>
                </tr>
                {open === r.pick_id && (
                  <tr className="border-b border-regla-suave">
                    <td colSpan={6} className="pb-4">
                      <PorQueFallo pickId={r.pick_id} />
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
