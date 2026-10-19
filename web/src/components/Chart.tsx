"use client";

import { BarChart, LineChart } from "echarts/charts";
import { GridComponent, MarkLineComponent, TooltipComponent } from "echarts/components";
import * as echarts from "echarts/core";
import type { EChartsCoreOption } from "echarts/core";
import { SVGRenderer } from "echarts/renderers";
import { useEffect, useRef, useSyncExternalStore } from "react";

echarts.use([BarChart, LineChart, GridComponent, TooltipComponent, MarkLineComponent, SVGRenderer]);

export interface ChartTheme {
  tinta: string;
  grafito: string;
  regla: string;
  reglaSuave: string;
  hoja: string;
  boli: string;
  boliSuave: string;
  rojo: string;
  tarjeta: string;
  font: string;
}

const DARK = "(prefers-color-scheme: dark)";

function subscribe(cb: () => void) {
  const mq = window.matchMedia(DARK);
  mq.addEventListener("change", cb);
  return () => mq.removeEventListener("change", cb);
}

function readTheme(): string {
  const s = getComputedStyle(document.documentElement);
  const v = (name: string) => s.getPropertyValue(name).trim();
  return JSON.stringify({
    tinta: v("--tinta"),
    grafito: v("--grafito"),
    regla: v("--regla"),
    reglaSuave: v("--regla-suave"),
    hoja: v("--hoja"),
    boli: v("--boli"),
    boliSuave: v("--boli-suave"),
    rojo: v("--rojo"),
    tarjeta: v("--tarjeta"),
    font: getComputedStyle(document.body).fontFamily,
  } satisfies ChartTheme);
}

/** Colores del tema actual (claro u oscuro) leídos de las variables CSS */
export function useChartTheme(): ChartTheme | null {
  const raw = useSyncExternalStore(subscribe, readTheme, () => "");
  return raw ? (JSON.parse(raw) as ChartTheme) : null;
}

/** Ejes y rejilla comunes a todas las gráficas */
export function baseOption(t: ChartTheme): EChartsCoreOption {
  return {
    animationDuration: 400,
    textStyle: { fontFamily: t.font, color: t.grafito },
    grid: { left: 8, right: 16, top: 16, bottom: 8, containLabel: true },
    tooltip: {
      backgroundColor: t.hoja,
      borderColor: t.regla,
      textStyle: { color: t.tinta, fontFamily: t.font },
      extraCssText: "box-shadow:none;border-radius:4px;",
    },
  };
}

export function Chart({
  option,
  height = 220,
  label,
}: {
  option: EChartsCoreOption | null;
  height?: number;
  label: string;
}) {
  const ref = useRef<HTMLDivElement>(null);
  const chart = useRef<echarts.ECharts | null>(null);

  useEffect(() => {
    if (!ref.current) return;
    const c = echarts.init(ref.current, null, { renderer: "svg" });
    chart.current = c;
    const ro = new ResizeObserver(() => c.resize());
    ro.observe(ref.current);
    return () => {
      ro.disconnect();
      c.dispose();
      chart.current = null;
    };
  }, []);

  useEffect(() => {
    if (chart.current && option) {
      const reduce = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
      chart.current.setOption({ ...option, animation: !reduce && option.animation !== false }, true);
    }
  }, [option]);

  return <div ref={ref} role="img" aria-label={label} style={{ height, width: "100%" }} />;
}
