#!/usr/bin/env node
// Contraste de la paleta del panel (web/src/app/globals.css) en tema claro y oscuro, según WCAG 2.
//   node .claude/skills/disenio-panel/paleta.mjs            → tabla de contrastes de cada texto sobre cada fondo
//   node .claude/skills/disenio-panel/paleta.mjs --fallos   → solo las combinaciones que se usan y no llegan
import { readFileSync } from "node:fs";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";

const ROOT = resolve(dirname(fileURLToPath(import.meta.url)), "../../..");
const css = readFileSync(join(ROOT, "web/src/app/globals.css"), "utf8");

function tokens(block) {
  return Object.fromEntries([...block.matchAll(/--([a-z-]+):\s*(#[0-9a-f]{6})/gi)].map((m) => [m[1], m[2]]));
}
const light = tokens(css.match(/:root\s*{([^}]*)}/)[1]);
const dark = { ...light, ...tokens(css.match(/prefers-color-scheme:\s*dark\)\s*{\s*:root\s*{([^}]*)}/)[1]) };

const lum = (hex) => {
  const c = [1, 3, 5].map((i) => parseInt(hex.slice(i, i + 2), 16) / 255);
  const f = (v) => (v <= 0.03928 ? v / 12.92 : ((v + 0.055) / 1.055) ** 2.4);
  return 0.2126 * f(c[0]) + 0.7152 * f(c[1]) + 0.0722 * f(c[2]);
};
const ratio = (a, b) => {
  const [x, y] = [lum(a), lum(b)].sort((p, q) => q - p);
  return (x + 0.05) / (y + 0.05);
};

const TEXTS = ["tinta", "grafito", "boli", "rojo", "tarjeta"];
const BACKS = ["papel", "hoja", "regla-suave", "boli-suave", "rojo-suave", "tarjeta-suave"];
// Combinaciones que el panel usa de verdad (texto sobre fondo) y el mínimo que deben cumplir
const USED = [
  ["tinta", "papel", 4.5], ["tinta", "hoja", 4.5], ["grafito", "papel", 4.5], ["grafito", "hoja", 4.5],
  ["boli", "papel", 4.5], ["boli", "hoja", 4.5], ["boli", "boli-suave", 4.5], ["rojo", "papel", 4.5],
  ["rojo", "hoja", 4.5], ["rojo", "rojo-suave", 4.5], ["tinta", "tarjeta-suave", 4.5],
  ["tarjeta", "papel", 3], // borde de aviso: elemento gráfico con significado (WCAG 1.4.11, 3:1)
  ["tarjeta", "hoja", 3],
  ["regla", "papel", 1.2], // separadores decorativos: solo tienen que notarse
];

const onlyFails = process.argv.includes("--fallos");
for (const [name, t] of [["claro", light], ["oscuro", dark]]) {
  console.log(`\n== Tema ${name}`);
  if (!onlyFails) {
    console.log(`${"texto \\ fondo".padEnd(14)}${BACKS.map((b) => b.padStart(14)).join("")}`);
    for (const fg of TEXTS) {
      console.log(fg.padEnd(14) + BACKS.map((bg) => ratio(t[fg], t[bg]).toFixed(2).padStart(14)).join(""));
    }
  }
  const fails = USED.filter(([fg, bg, min]) => ratio(t[fg], t[bg]) < min);
  console.log(fails.length
    ? `No llegan: ${fails.map(([fg, bg, min]) => `${fg} sobre ${bg} ${ratio(t[fg], t[bg]).toFixed(2)}:1 (mín. ${min})`).join("; ")}`
    : "Todas las combinaciones usadas cumplen.");
}
