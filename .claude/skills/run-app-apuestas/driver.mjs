#!/usr/bin/env node
// Driver del panel web de App Apuestas: abre las páginas en Brave sin ventana (playwright-core), saca capturas
// y hace una auditoría de diseño y usabilidad. Lo usan las skills run-app-apuestas y disenio-panel.
//
//   node .claude/skills/run-app-apuestas/driver.mjs check
//   node .claude/skills/run-app-apuestas/driver.mjs shots [--pages hoy,partido] [--devices desktop,mobile] [--schemes light,dark]
//   node .claude/skills/run-app-apuestas/driver.mjs shot /evaluar?partido=4821 [--mobile] [--dark] [--name evaluar-real]
//   node .claude/skills/run-app-apuestas/driver.mjs audit [--pages ...] [--devices ...] [--schemes ...]
//
// Variables: APUESTAS_WEB (http://localhost:3000), APUESTAS_API (http://127.0.0.1:8000),
// BROWSER (/usr/bin/brave-origin), SHOTS_DIR (/tmp/apuestas-shots).

import { mkdirSync, writeFileSync } from "node:fs";
import { createRequire } from "node:module";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const require = createRequire(join(ROOT, "web/package.json"));
const { chromium } = require("playwright-core");

const WEB = process.env.APUESTAS_WEB ?? "http://localhost:3000";
const API = process.env.APUESTAS_API ?? "http://127.0.0.1:8000";
const BROWSER = process.env.BROWSER ?? "/usr/bin/brave-origin";
const OUT = process.env.SHOTS_DIR ?? "/tmp/apuestas-shots";

const DEVICES = {
  desktop: { viewport: { width: 1280, height: 900 } },
  mobile: { viewport: { width: 390, height: 844 }, isMobile: true, hasTouch: true, deviceScaleFactor: 2 },
};
// Cada página y el texto que indica que ya cargó sus datos (no solo el esqueleto)
const PAGES = {
  hoy: { path: "/", ready: "Partidos del día" },
  // Las otras pestañas de Hoy, el día del primer partido próximo (hoy puede no haber partidos y salir vacías)
  "hoy-valor": { path: null, hash: "#valor", ready: "Otras apuestas con valor" },
  "hoy-props": { path: null, hash: "#props", ready: "Props con cuota mínima" },
  partidos: { path: "/partidos", ready: "vs" },
  // El primer partido de la lista, una entrada por pestaña (la pestaña va en el ancla de la URL)
  partido: { path: null, ready: "Alineación y bajas" },
  "partido-probabilidades": { path: null, hash: "#probabilidades", ready: "Dificultad del rival" },
  "partido-estadisticas": { path: null, hash: "#estadisticas", ready: "Estadísticas esperadas" },
  "partido-cuotas": { path: null, hash: "#cuotas", ready: "Props: cuota mínima" },
  "partido-jugadores": { path: null, hash: "#jugadores", ready: "Proyección para este partido" },
  evaluar: { path: null, ready: "Cuotas de Betano" }, // Evaluar con ese partido elegido
  capturas: { path: "/capturas", ready: "Arrastra aquí la captura" },
  rendimiento: { path: "/rendimiento", ready: "Banca" },
  datos: { path: "/datos", ready: "Fuentes" },
};

function args() {
  const [cmd = "help", ...rest] = process.argv.slice(2);
  const opts = { _: [] };
  for (let i = 0; i < rest.length; i++) {
    if (rest[i].startsWith("--")) {
      const key = rest[i].slice(2);
      opts[key] = rest[i + 1] && !rest[i + 1].startsWith("--") ? rest[++i] : true;
    } else opts._.push(rest[i]);
  }
  return { cmd, opts };
}

const list = (v, all) => (v && v !== true ? String(v).split(",") : all);

async function check() {
  for (const [name, url] of [["panel", WEB], ["api", `${API}/health`]]) {
    try {
      const r = await fetch(url);
      console.log(`${name}: ${url} → ${r.status}`);
    } catch (e) {
      console.log(`${name}: ${url} → SIN RESPUESTA (${e.cause?.code ?? e.message})`);
      process.exitCode = 1;
    }
  }
}

async function firstMatch() {
  const r = await fetch(`${API}/matches?days=10`);
  const rows = await r.json();
  if (!rows.length) throw new Error("La API no tiene partidos próximos (¿ingesta hecha?)");
  return rows[0];
}

// Día del partido en Lima (YYYY-MM-DD) a partir de kickoff_local («vie 23/10 13:30»), que no trae el año
function matchDay(m) {
  const [d, mo] = m.kickoff_local.split(" ")[1].split("/").map(Number);
  const now = new Date();
  const y = now.getFullYear() + (mo < now.getMonth() + 1 - 6 ? 1 : 0);
  return `${y}-${String(mo).padStart(2, "0")}-${String(d).padStart(2, "0")}`;
}

async function resolvePages(names) {
  const isMatch = (n) => n === "partido" || n.startsWith("partido-");
  const isHoyTab = (n) => n.startsWith("hoy-");
  const first = names.some((n) => isMatch(n) || isHoyTab(n) || n === "evaluar") ? await firstMatch() : null;
  const mid = first?.match_id;
  return names.map((n) => {
    const p = PAGES[n];
    if (!p) throw new Error(`Página desconocida: ${n} (hay: ${Object.keys(PAGES).join(", ")})`);
    const path = isMatch(n)
      ? `/partidos/${mid}${p.hash ?? ""}`
      : isHoyTab(n)
        ? `/?dia=${matchDay(first)}${p.hash}`
        : n === "evaluar"
          ? `/evaluar?partido=${mid}`
          : p.path;
    return { name: n, path, ready: p.ready };
  });
}

async function open(browser, device, scheme) {
  const ctx = await browser.newContext({ ...DEVICES[device], colorScheme: scheme, locale: "es-PE", timezoneId: "America/Lima" });
  const page = await ctx.newPage();
  const problems = [];
  page.on("console", (m) => m.type() === "error" && problems.push(`consola: ${m.text().slice(0, 200)}`));
  page.on("pageerror", (e) => problems.push(`excepción: ${e.message.slice(0, 200)}`));
  page.on("response", (r) => r.status() >= 400 && problems.push(`HTTP ${r.status()} ${r.url().replace(WEB, "")}`));
  return { ctx, page, problems };
}

async function visit(page, path, ready) {
  await page.goto(WEB + path, { waitUntil: "networkidle", timeout: 60000 });
  if (ready) await page.getByText(ready).first().waitFor({ timeout: 30000 });
  // Escudos y gráficos cargan perezosamente: recorrer la página y volver arriba
  await page.evaluate(async () => {
    for (let y = 0; y < document.body.scrollHeight; y += 700) {
      window.scrollTo(0, y);
      await new Promise((r) => setTimeout(r, 60));
    }
    window.scrollTo(0, 0);
  });
  await page.waitForLoadState("networkidle");
}

// Auditoría dentro de la página: devuelve números e inventario de diseño
function auditInPage(isMobile) {
  const parse = (c) => {
    const m = c.match(/rgba?\(([^)]+)\)/);
    if (!m) return null;
    const [r, g, b, a = 1] = m[1].split(/[ ,/]+/).filter(Boolean).map(Number);
    return { r, g, b, a };
  };
  const lum = ({ r, g, b }) => {
    const f = (v) => ((v /= 255) <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
    return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
  };
  const bgOf = (el) => {
    for (let n = el; n; n = n.parentElement) {
      const c = parse(getComputedStyle(n).backgroundColor);
      if (c && c.a > 0.5) return c;
    }
    return parse(getComputedStyle(document.body).backgroundColor);
  };
  const visible = (el) => {
    const r = el.getBoundingClientRect();
    const s = getComputedStyle(el);
    return r.width > 0 && r.height > 0 && s.visibility !== "hidden" && s.display !== "none" && Number(s.opacity) > 0.1;
  };
  const label = (el) => (el.textContent || el.getAttribute("aria-label") || el.tagName).trim().replace(/\s+/g, " ").slice(0, 50);

  const out = { overflow: [], smallText: [], lowContrast: [], smallTargets: [], imgNoAlt: 0, unlabeled: [] };
  const inv = { fonts: {}, sizes: {}, weights: {}, colors: {}, backgrounds: {}, radii: {}, shadows: {}, motion: {} };
  const bump = (o, k) => (o[k] = (o[k] || 0) + 1);
  const W = document.documentElement.clientWidth;
  out.pageOverflowPx = Math.max(0, document.documentElement.scrollWidth - W);

  for (const el of document.querySelectorAll("body *")) {
    if (!visible(el)) continue;
    const s = getComputedStyle(el);
    const r = el.getBoundingClientRect();
    if (r.right > W + 1 && s.position !== "fixed" && !el.closest("[class*=overflow-x-auto]")) {
      out.overflow.push(`${el.tagName.toLowerCase()} «${label(el)}» ancho ${Math.round(r.right)}px`);
    }
    if (s.borderRadius !== "0px") bump(inv.radii, parseFloat(s.borderRadius) > 999 ? "redondo (rounded-full)" : s.borderRadius);
    if (s.boxShadow !== "none") bump(inv.shadows, s.boxShadow.slice(0, 60));
    const bg = parse(s.backgroundColor);
    if (bg && bg.a > 0) bump(inv.backgrounds, s.backgroundColor);
    if (s.transitionDuration !== "0s" || s.animationName !== "none") {
      const what = s.animationName !== "none"
        ? `animación ${s.animationName} ${s.animationDuration} ${s.animationTimingFunction}`
        : `transición ${s.transitionProperty.split(",").length > 3 ? "colores" : s.transitionProperty} ${s.transitionDuration} ${s.transitionTimingFunction}`;
      bump(inv.motion, `${el.tagName.toLowerCase()}: ${what}`);
    }
    const ownText = [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim());
    if (ownText) {
      const size = parseFloat(s.fontSize);
      bump(inv.fonts, s.fontFamily.split(",")[0].replace(/["']/g, "").trim());
      bump(inv.sizes, `${size}px`);
      bump(inv.weights, s.fontWeight);
      bump(inv.colors, s.color);
      if (size < 12) out.smallText.push(`${size}px «${label(el)}»`);
      const fg = parse(s.color);
      const back = bgOf(el);
      // El texto decorativo (aria-hidden, como el «0.00» tachado de «Hoy no hay apuesta») no pide contraste en WCAG
      if (fg && back && !el.closest('[aria-hidden="true"]')) {
        const [a, b] = [lum(fg), lum(back)].sort((x, y) => y - x);
        const ratio = (a + 0.05) / (b + 0.05);
        const large = size >= 24 || (size >= 18.66 && Number(s.fontWeight) >= 700);
        if (ratio < (large ? 3 : 4.5)) out.lowContrast.push(`${ratio.toFixed(2)}:1 «${label(el)}» ${s.color} sobre rgb(${back.r},${back.g},${back.b})`);
      }
    }
    const interactive = el.matches("a[href], button, input:not([type=hidden]), select, textarea, summary, [role=button]");
    // Los controles ocultos (radios y archivo sr-only) se tocan por su <label>: no cuentan
    if (interactive && r.width > 2 && r.height > 2) {
      if (isMobile && (r.width < 24 || r.height < 24) && !el.closest("p, li, td")) out.smallTargets.push(`${Math.round(r.width)}x${Math.round(r.height)} «${label(el)}»`);
      if (!label(el) && !el.labels?.length) out.unlabeled.push(el.outerHTML.slice(0, 80));
    }
    if (el.tagName === "IMG" && !el.hasAttribute("alt")) out.imgNoAlt++;
  }
  let reducedMotion = false;
  for (const sheet of document.styleSheets) {
    try {
      for (const rule of sheet.cssRules) if (rule.media?.mediaText?.includes("prefers-reduced-motion")) reducedMotion = true;
    } catch {
      /* hoja de otro origen */
    }
  }
  const top = (o, n = 12) => Object.entries(o).sort((a, b) => b[1] - a[1]).slice(0, n);
  return {
    pageOverflowPx: out.pageOverflowPx,
    overflow: out.overflow.slice(0, 8),
    smallText: [out.smallText.length, out.smallText.slice(0, 6)],
    lowContrast: [out.lowContrast.length, out.lowContrast.slice(0, 8)],
    smallTargets: [out.smallTargets.length, out.smallTargets.slice(0, 8)],
    unlabeled: out.unlabeled.slice(0, 5),
    imgNoAlt: out.imgNoAlt,
    reducedMotionRule: reducedMotion,
    inventory: {
      fonts: top(inv.fonts), sizes: top(inv.sizes, 20), weights: top(inv.weights), colors: top(inv.colors),
      backgrounds: top(inv.backgrounds), radii: top(inv.radii), shadows: top(inv.shadows, 6), motion: top(inv.motion, 10),
    },
  };
}

async function run(cmd, opts) {
  mkdirSync(OUT, { recursive: true });
  const browser = await chromium.launch({ executablePath: BROWSER, headless: true });
  const results = [];
  try {
    if (cmd === "shot") {
      const path = opts._[0] ?? "/";
      const device = opts.mobile ? "mobile" : "desktop";
      const scheme = opts.dark ? "dark" : "light";
      const { ctx, page, problems } = await open(browser, device, scheme);
      await visit(page, path, opts.ready);
      const file = join(OUT, `${opts.name ?? (path.replace(/[^a-z0-9]+/gi, "-").replace(/^-|-$/g, "") || "hoy")}-${device}-${scheme}.png`);
      await page.screenshot({ path: file, fullPage: !opts.viewport });
      console.log(file, problems.length ? `\n  problemas: ${problems.join(" | ")}` : "");
      await ctx.close();
      return;
    }
    const pages = await resolvePages(list(opts.pages, Object.keys(PAGES)));
    for (const device of list(opts.devices, Object.keys(DEVICES))) {
      for (const scheme of list(opts.schemes, cmd === "audit" ? ["light"] : ["light", "dark"])) {
        for (const p of pages) {
          const { ctx, page, problems } = await open(browser, device, scheme);
          const t0 = Date.now();
          try {
            await visit(page, p.path, p.ready);
          } catch (e) {
            problems.push(`no cargó: ${e.message.split("\n")[0]}`);
          }
          const file = join(OUT, `${p.name}-${device}-${scheme}.png`);
          await page.screenshot({ path: file, fullPage: true });
          const row = { page: p.name, path: p.path, device, scheme, ms: Date.now() - t0, file, problems };
          if (cmd === "audit") row.audit = await page.evaluate(auditInPage, device === "mobile");
          results.push(row);
          const a = row.audit;
          console.log(
            `${p.name.padEnd(12)} ${device.padEnd(7)} ${scheme.padEnd(5)} ${String(row.ms).padStart(5)} ms  ${file}` +
              (a ? `\n   desborde ${a.pageOverflowPx}px · texto <12px ${a.smallText[0]} · contraste bajo ${a.lowContrast[0]} · toques <24px ${a.smallTargets[0]} · img sin alt ${a.imgNoAlt}` : "") +
              (problems.length ? `\n   problemas: ${problems.slice(0, 5).join(" | ")}` : ""),
          );
          await ctx.close();
        }
      }
    }
    if (cmd === "audit") {
      writeFileSync(join(OUT, "audit.json"), JSON.stringify(results, null, 1));
      console.log(`\nDetalle e inventario de diseño: ${join(OUT, "audit.json")}`);
    }
  } finally {
    await browser.close();
  }
}

const { cmd, opts } = args();
if (cmd === "check") await check();
else if (["shots", "shot", "audit"].includes(cmd)) await run(cmd, opts);
else console.log("Uso: driver.mjs check | shots | shot <ruta> [--mobile] [--dark] | audit   (ver SKILL.md)");
