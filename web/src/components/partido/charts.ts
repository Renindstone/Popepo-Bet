import type { EChartsCoreOption } from "echarts/core";
import { baseOption, type ChartTheme } from "@/components/Chart";
import { pct } from "@/lib/format";
import type { StatSummary } from "@/lib/types";

const pctAxis = (t: ChartTheme) => ({
  type: "value",
  min: 0,
  max: 1,
  interval: 0.25,
  axisLabel: { formatter: (v: number) => pct(v), color: t.grafito },
  splitLine: { lineStyle: { color: t.reglaSuave } },
});

const catAxis = (t: ChartTheme, data: string[], name?: string) => ({
  type: "category",
  data,
  name,
  nameLocation: "middle",
  nameGap: 28,
  nameTextStyle: { color: t.grafito },
  axisTick: { show: false },
  axisLine: { lineStyle: { color: t.regla } },
  axisLabel: { color: t.tinta },
});

const halfLine = (t: ChartTheme) => ({
  silent: true,
  symbol: "none",
  label: { show: false },
  lineStyle: { color: t.grafito, type: "dashed", width: 1 },
  data: [{ yAxis: 0.5 }],
});

/** Probabilidad de que haya más de X goles */
export function overGoalsOption(t: ChartTheme, over: Record<string, number>): EChartsCoreOption {
  const lines = Object.keys(over);
  return {
    ...baseOption(t),
    grid: { left: 8, right: 8, top: 24, bottom: 28, containLabel: true },
    tooltip: { ...(baseOption(t).tooltip as object), trigger: "axis", valueFormatter: (v: number) => pct(v) },
    xAxis: catAxis(t, lines, "Más de … goles"),
    yAxis: pctAxis(t),
    series: [
      {
        type: "bar",
        name: "Probabilidad",
        data: lines.map((l) => over[l]),
        barWidth: "52%",
        itemStyle: { color: t.tinta, borderRadius: [2, 2, 0, 0] },
        label: { show: true, position: "top", color: t.tinta, formatter: (p: { value: number }) => pct(p.value) },
        markLine: halfLine(t),
      },
    ],
  };
}

/** Hándicap asiático del local: probabilidad de cubrir cada línea (sin contar devoluciones) */
export function handicapOption(t: ChartTheme, ah: Record<string, number>, home: string): EChartsCoreOption {
  const lines = Object.keys(ah).sort((a, b) => Number(a) - Number(b));
  const label = (l: string) => (Number(l) > 0 ? `+${Number(l)}` : String(Number(l)));
  return {
    ...baseOption(t),
    grid: { left: 8, right: 8, top: 24, bottom: 28, containLabel: true },
    tooltip: { ...(baseOption(t).tooltip as object), trigger: "axis", valueFormatter: (v: number) => pct(v) },
    xAxis: catAxis(t, lines.map(label), `Línea de ${home}`),
    yAxis: pctAxis(t),
    series: [
      {
        type: "bar",
        name: `${home} cubre`,
        data: lines.map((l) => ah[l]),
        barWidth: "52%",
        itemStyle: { color: t.grafito, borderRadius: [2, 2, 0, 0] },
        label: { show: true, position: "top", color: t.tinta, formatter: (p: { value: number }) => pct(p.value) },
        markLine: halfLine(t),
      },
    ],
  };
}

/** Marcadores más probables */
export function scoresOption(t: ChartTheme, scores: { score: string; prob: number }[]): EChartsCoreOption {
  const rows = [...scores].reverse();
  const max = Math.max(...scores.map((s) => s.prob), 0.01);
  return {
    ...baseOption(t),
    grid: { left: 8, right: 48, top: 4, bottom: 4, containLabel: true },
    tooltip: { ...(baseOption(t).tooltip as object), trigger: "axis", valueFormatter: (v: number) => pct(v, 1) },
    xAxis: { type: "value", show: false, max: max * 1.05 },
    yAxis: { ...catAxis(t, rows.map((s) => s.score)), axisLine: { show: false }, axisLabel: { color: t.tinta, fontWeight: 600 } },
    series: [
      {
        type: "bar",
        name: "Probabilidad",
        data: rows.map((s) => s.prob),
        barWidth: "56%",
        itemStyle: { color: t.tinta, borderRadius: [0, 2, 2, 0] },
        label: { show: true, position: "right", color: t.grafito, formatter: (p: { value: number }) => pct(p.value, 1) },
      },
    ],
  };
}

export const STAT_NAMES: Record<string, string> = {
  shots: "Remates",
  shots_on_target: "Remates a puerta",
  corners: "Córners",
  fouls: "Faltas",
  cards: "Tarjetas",
  offsides: "Offsides",
};

/**
 * Reparto de cada estadística entre los dos equipos (barras al 100 %), con el valor esperado
 * de cada uno como etiqueta. Así se comparan estadísticas de escalas muy distintas.
 */
export function statsShareOption(
  t: ChartTheme,
  stats: Record<string, StatSummary>,
  home: string,
  away: string,
): EChartsCoreOption {
  const keys = Object.keys(STAT_NAMES).filter((k) => stats[k]).reverse();
  const share = (k: string, side: "home" | "away") => {
    const e = stats[k].expected;
    return e.home + e.away > 0 ? e[side] / (e.home + e.away) : 0.5;
  };
  const lbl = (side: "home" | "away") => ({
    show: true,
    position: side === "home" ? "insideLeft" : "insideRight",
    color: side === "home" ? t.hoja : t.tinta,
    fontWeight: 600,
    formatter: (p: { dataIndex: number }) => stats[keys[p.dataIndex]].expected[side].toFixed(1),
  });
  return {
    ...baseOption(t),
    grid: { left: 8, right: 8, top: 4, bottom: 4, containLabel: true },
    tooltip: {
      ...(baseOption(t).tooltip as object),
      trigger: "axis",
      axisPointer: { type: "none" },
      formatter: (ps: { dataIndex: number }[]) => {
        const k = keys[ps[0].dataIndex];
        const e = stats[k].expected;
        return `${STAT_NAMES[k]}<br/>${home}: ${e.home.toFixed(1)}<br/>${away}: ${e.away.toFixed(1)}<br/>Total: ${e.total.toFixed(1)}`;
      },
    },
    xAxis: { type: "value", show: false, max: 1 },
    yAxis: { ...catAxis(t, keys.map((k) => STAT_NAMES[k])), axisLine: { show: false } },
    series: [
      {
        type: "bar",
        name: home,
        stack: "reparto",
        data: keys.map((k) => share(k, "home")),
        barWidth: "62%",
        itemStyle: { color: t.tinta },
        label: lbl("home"),
      },
      {
        type: "bar",
        name: away,
        stack: "reparto",
        data: keys.map((k) => share(k, "away")),
        itemStyle: { color: t.regla },
        label: lbl("away"),
        markLine: {
          silent: true,
          symbol: "none",
          label: { show: false },
          lineStyle: { color: t.hoja, width: 1 },
          data: [{ xAxis: 0.5 }],
        },
      },
    ],
  };
}
