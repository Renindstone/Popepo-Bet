"use client";

import type { EChartsCoreOption } from "echarts/core";
import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useMemo } from "react";
import { baseOption, Chart, type ChartTheme, useChartTheme } from "@/components/Chart";
import { Empty, ErrorNote, Figure, Loading, PageTitle, Section, Tag } from "@/components/ui";
import { useApi } from "@/lib/api";
import { competitionName, int, money, odds, pct, resultText, shortDate, signedPct, splitMatch } from "@/lib/format";
import { betLabel, bookmakerName, marketName } from "@/lib/markets";
import type { Aggregate, Bankroll, Performance, PickHistory, UserBet } from "@/lib/types";

const PERIODS = [
  { value: "", label: "Todo" },
  { value: "7", label: "7 días" },
  { value: "30", label: "30 días" },
  { value: "90", label: "90 días" },
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
        title="Mis apuestas"
        sub="Tu rendimiento real con las apuestas que registras. Se liquidan solas cuando termina el partido."
        actions={
          <fieldset className="flex flex-wrap gap-1">
            <legend className="sr-only">Periodo</legend>
            {PERIODS.map((o) => (
              <button
                key={o.value}
                type="button"
                aria-pressed={days === o.value}
                onClick={() => setDays(o.value)}
                className={`h-9 rounded-[3px] border px-3 text-[0.9rem] font-semibold ${
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
          <Banca b={p.bankroll} />
          <Evolucion bets={bets.data} currency={currency} />
          <Desglose p={p} currency={currency} />
        </>
      )}

      <Section title="Últimas apuestas registradas">
        {bets.error ? (
          <ErrorNote error={bets.error} onRetry={() => bets.mutate()} />
        ) : !bets.data ? (
          <Loading lines={3} />
        ) : bets.data.length === 0 ? (
          <Empty>
            Aún no registras ninguna apuesta. Cuando hagas una, regístrala desde{" "}
            <Link href="/evaluar" className="font-semibold text-boli underline underline-offset-4">
              Evaluar cuota
            </Link>{" "}
            para seguir tu ROI y tu CLV.
          </Empty>
        ) : (
          <BetsTable rows={bets.data} currency={currency} />
        )}
      </Section>

      <Section
        title="La apuesta del día del sistema"
        intro="Cómo le fue a la apuesta del día en el último año, con 1 unidad por apuesta. Mide al sistema, no a ti: sirve para decidir cuánto confiar en él."
      >
        {history.error ? (
          <ErrorNote error={history.error} onRetry={() => history.mutate()} />
        ) : !history.data ? (
          <Loading lines={3} />
        ) : (
          <Historial h={history.data} />
        )}
      </Section>
    </>
  );
}

// --------------------------------------------------------------------------- resumen y banca

function Resumen({ total, currency }: { total: Aggregate; currency: string }) {
  const tone = (x: number | null) => (x == null || x === 0 ? undefined : x > 0 ? "boli" : "rojo");
  return (
    <Section
      title="Resumen"
      intro="El CLV compara tu cuota con la de cierre. Un CLV positivo y sostenido es la mejor señal de que apuestas con criterio, aunque el resultado tarde en reflejarlo."
    >
      {total.bets === 0 ? (
        <Empty>Sin apuestas liquidadas en este periodo.</Empty>
      ) : (
        <div className="grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-4 lg:grid-cols-7">
          <Figure size="lg" value={money(total.profit, currency, true)} label="beneficio" tone={tone(total.profit)} />
          <Figure size="lg" value={signedPct(total.roi)} label="ROI" tone={tone(total.roi)} />
          <Figure size="lg" value={signedPct(total.avg_clv)} label="CLV medio" tone={tone(total.avg_clv)} />
          <Figure value={pct(total.hit_rate)} label="acierto" />
          <Figure value={int(total.bets)} label="apuestas liquidadas" />
          <Figure value={money(total.staked, currency)} label="apostado" />
          <Figure value={odds(total.avg_odds)} label="cuota media" />
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
        <span className={`cond num text-[1.6rem] font-bold ${profit > 0 ? "text-boli" : profit < 0 ? "text-rojo" : ""}`}>
          {money(profit, currency, true)}
        </span>
      </div>
      <div
        className="mt-1.5 h-2 rounded-full bg-regla-suave"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={Math.round(used * 100)}
        aria-label={`${label}: ${pct(used)} del límite de pérdida usado`}
      >
        <div className={`h-2 rounded-full ${tone}`} style={{ width: `${used * 100}%` }} />
      </div>
      <p className="mt-1 text-[0.88rem] text-grafito">
        {profit >= 0
          ? `Sin pérdidas. Límite de pérdida: ${money(-limit, currency)}`
          : `Usado el ${pct(used)} del límite de pérdida de ${money(-limit, currency)}`}
      </p>
    </div>
  );
}

function Banca({ b }: { b: Bankroll }) {
  return (
    <Section title="Banca" intro="Los límites de pérdida diaria y semanal salen de tu configuración. Al llegar a uno, para.">
      <div className="grid gap-x-10 gap-y-6 md:grid-cols-[auto_minmax(0,1fr)_minmax(0,1fr)]">
        <div className="grid grid-cols-2 gap-x-8 gap-y-4 md:grid-cols-1">
          <Figure size="lg" value={money(b.bankroll, b.currency)} label="banca" />
          <Figure value={int(b.pending_bets)} label={`pendientes de liquidar, ${money(b.pending_stake, b.currency)} en juego`} />
        </div>
        <LossMeter label="Hoy" profit={b.day_profit} limit={b.daily_loss_limit} currency={b.currency} />
        <LossMeter label="Esta semana" profit={b.week_profit} limit={b.weekly_loss_limit} currency={b.currency} />
      </div>
      {b.warnings.map((w) => (
        <p key={w} role="alert" className="mt-4 border-l-[3px] border-rojo bg-rojo-suave px-3 py-2 font-semibold">
          {w}
        </p>
      ))}
    </Section>
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
      name: "Apuesta n.º",
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
        name: "Beneficio acumulado",
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
    <Section title="Beneficio acumulado" intro="Con tus últimas 30 apuestas registradas, en el orden en que las hiciste.">
      {values.length < 2 ? (
        <Empty>Hacen falta al menos dos apuestas liquidadas para dibujar la evolución.</Empty>
      ) : (
        <Chart option={option} height={260} label="Beneficio acumulado apuesta a apuesta" />
      )}
    </Section>
  );
}

// --------------------------------------------------------------------------- desglose

function Desglose({ p, currency }: { p: Performance; currency: string }) {
  if (p.total.bets === 0) return null;
  return (
    <Section title="Desglose" intro="Dónde ganas y dónde pierdes. Con pocas apuestas por grupo, el ROI es sobre todo ruido.">
      <div className="grid gap-x-10 gap-y-10 lg:grid-cols-2">
        <Grupo title="Por mercado" data={p.market} name={marketLabel} currency={currency} chart />
        <Grupo title="Por competición" data={p.competition} name={competitionName} currency={currency} chart />
        <Grupo title="Por casa" data={p.bookmaker} name={bookmakerName} currency={currency} />
        <Grupo title="Por rango de cuota" data={p.odds_band} name={oddsBand} currency={currency} />
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
        <table className="w-full min-w-[460px] border-collapse text-[0.92rem]">
          <thead>
            <tr className="border-b border-regla text-right text-[0.85rem] text-grafito">
              <th className="py-1.5 pr-3 text-left font-medium">Grupo</th>
              <th className="py-1.5 pr-3 font-medium">Apuestas</th>
              <th className="py-1.5 pr-3 font-medium">Beneficio</th>
              <th className="py-1.5 pr-3 font-medium">ROI</th>
              <th className="py-1.5 pr-3 font-medium">Acierto</th>
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

const RESULT_TONE: Record<string, "boli" | "rojo" | "neutral"> = {
  win: "boli",
  half_win: "boli",
  loss: "rojo",
  half_loss: "rojo",
};

function profitClass(x: number | null | undefined): string {
  return x != null && x > 0 ? "text-boli" : x != null && x < 0 ? "text-rojo" : "";
}

function BetsTable({ rows, currency }: { rows: UserBet[]; currency: string }) {
  return (
    <>
      <ul className="divide-y divide-regla-suave border-y border-regla-suave md:hidden">
        {rows.map((b) => {
          const [home, away] = splitMatch(b.match);
          return (
            <li key={b.bet_id} className="py-3">
              <div className="flex items-start justify-between gap-4">
                <span className="font-semibold">{betLabel(b.market, b.selection, b.line, { home, away })}</span>
                <span className="cond num text-2xl leading-none font-bold">{odds(b.odds)}</span>
              </div>
              <p className="mt-0.5 text-[0.88rem] text-grafito">
                {b.match}, en {bookmakerName(b.bookmaker)}
              </p>
              <p className="num mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-[0.9rem]">
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
      <table className="w-full min-w-[760px] border-collapse text-[0.95rem]">
        <thead>
          <tr className="border-b border-regla text-left text-[0.85rem] text-grafito">
            <th className="py-2 pr-4 font-medium">Partido</th>
            <th className="py-2 pr-4 font-medium">Apuesta</th>
            <th className="py-2 pr-4 text-right font-medium">Cuota</th>
            <th className="py-2 pr-4 text-right font-medium">Importe</th>
            <th className="py-2 pr-4 font-medium">Resultado</th>
            <th className="py-2 pr-4 text-right font-medium">Beneficio</th>
            <th className="py-2 text-right font-medium">CLV</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((b) => {
            const [home, away] = splitMatch(b.match);
            return (
              <tr key={b.bet_id} className="border-b border-regla-suave">
                <td className="py-2 pr-4">{b.match}</td>
                <td className="py-2 pr-4">
                  {betLabel(b.market, b.selection, b.line, { home, away })}
                  <span className="block text-[0.85rem] text-grafito">{bookmakerName(b.bookmaker)}</span>
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

function Historial({ h }: { h: PickHistory }) {
  if (h.picks === 0) {
    return (
      <Empty>
        Aún no hay apuestas del día liquidadas. El historial empieza a llenarse a medida que el sistema elige una y el
        partido termina.
      </Empty>
    );
  }
  return (
    <>
      <div className="grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-5">
        <Figure value={int(h.picks)} label="apuestas del día" />
        <Figure
          value={`${h.profit_units > 0 ? "+" : ""}${h.profit_units.toFixed(2)} u`}
          label="beneficio en unidades"
          tone={h.profit_units > 0 ? "boli" : h.profit_units < 0 ? "rojo" : undefined}
        />
        <Figure value={signedPct(h.roi)} label="ROI" />
        <Figure value={pct(h.hit_rate)} label="acierto" />
        <Figure value={signedPct(h.avg_clv)} label="CLV medio" />
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
              <p className="mt-0.5 text-[0.88rem] text-grafito">
                {shortDate(r.date)}, {r.match}
              </p>
              <p className="num mt-1.5 flex flex-wrap items-center gap-x-4 text-[0.9rem]">
                <Tag tone={r.result ? RESULT_TONE[r.result] ?? "neutral" : "tarjeta"}>{resultText(r.result)}</Tag>
                {r.clv != null && <span className="text-grafito">CLV {signedPct(r.clv)}</span>}
              </p>
            </li>
          );
        })}
      </ul>
      <div className="mt-6 hidden overflow-x-auto md:block">
        <table className="w-full min-w-[640px] border-collapse text-[0.95rem]">
          <thead>
            <tr className="border-b border-regla text-left text-[0.85rem] text-grafito">
              <th className="py-2 pr-4 font-medium">Fecha</th>
              <th className="py-2 pr-4 font-medium">Partido</th>
              <th className="py-2 pr-4 font-medium">Apuesta</th>
              <th className="py-2 pr-4 text-right font-medium">Cuota</th>
              <th className="py-2 pr-4 font-medium">Resultado</th>
              <th className="py-2 text-right font-medium">CLV</th>
            </tr>
          </thead>
          <tbody>
            {[...h.last].reverse().map((r, i) => {
              const [home, away] = splitMatch(r.match);
              return (
                <tr key={i} className="border-b border-regla-suave">
                  <td className="num py-2 pr-4">{shortDate(r.date)}</td>
                  <td className="py-2 pr-4">{r.match}</td>
                  <td className="py-2 pr-4">{betLabel(r.market, r.selection, r.line, { home, away })}</td>
                  <td className="cond num py-2 pr-4 text-right text-lg font-bold">{odds(r.odds)}</td>
                  <td className="py-2 pr-4">
                    <Tag tone={r.result ? RESULT_TONE[r.result] ?? "neutral" : "tarjeta"}>{resultText(r.result)}</Tag>
                  </td>
                  <td className="num py-2 text-right">{signedPct(r.clv)}</td>
                </tr>
              );
            })}
          </tbody>
        </table>
      </div>
    </>
  );
}
