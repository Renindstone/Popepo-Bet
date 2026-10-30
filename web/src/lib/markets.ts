// Mercados: nombres en español y opciones del formulario de evaluación

import { lineText } from "./format";
import type { ClvRef } from "./types";

const STATS: Record<string, string> = {
  goals: "Goles",
  shots: "Remates",
  sot: "Remates a puerta",
  shots_on_target: "Remates a puerta",
  corners: "Córners",
  cards: "Tarjetas",
  fouls: "Faltas",
  offsides: "Offsides",
};

const PLAYER: Record<string, string> = {
  player_shots: "Remates de",
  player_sot: "Remates a puerta de",
  player_fouls: "Faltas de",
  player_goal: "Gol de",
  player_assist: "Asistencia de",
  player_goal_assist: "Gol o asistencia de",
  player_card: "Tarjeta para",
};

const BASE: Record<string, string> = {
  combo: "Combinada",
  "1x2": "Resultado",
  dc: "Doble oportunidad",
  dnb: "Empate no válido",
  btts: "Ambos marcan",
  ah: "Hándicap asiático",
  eh: "Hándicap (3 vías)",
};

export interface Teams {
  home?: string;
  away?: string;
  player?: string | null;
}

export function marketName(market: string, t: Teams = {}): string {
  if (BASE[market]) return BASE[market];
  if (market.startsWith("player_")) return `${PLAYER[market] ?? market} ${t.player ?? "jugador"}`;
  let rest = market;
  let scope: "home" | "away" | null = null;
  for (const sc of ["home", "away"] as const) {
    if (rest.endsWith(`_${sc}`)) {
      rest = rest.slice(0, -sc.length - 1);
      scope = sc;
    }
  }
  const [kind, ...statParts] = rest.split("_");
  const stat = STATS[statParts.join("_")] ?? statParts.join("_");
  const team = scope === "home" ? t.home ?? "local" : scope === "away" ? t.away ?? "visitante" : null;
  if (kind === "ou") return team ? `${stat} de ${team}` : stat;
  if (kind === "ah") return `Hándicap de ${stat.toLowerCase()}`;
  if (kind === "1x2") return `Más ${stat.toLowerCase()}`;
  return market;
}

export function selectionText(market: string, selection: string, line: number | null, t: Teams = {}): string {
  const home = t.home ?? "Local";
  const away = t.away ?? "Visitante";
  const ln = lineText(market, line);
  // Hándicap 3 vías: la línea se guarda como la del local; al visitante se le muestra la suya ("Coventry +2")
  const awayLn = market === "eh" && line != null ? lineText(market, -line) : ln;
  switch (selection) {
    case "home":
      return ln ? `${home} ${ln}` : home;
    case "away":
      return awayLn ? `${away} ${awayLn}` : away;
    case "draw":
      return market === "eh" && ln ? `Empate (${home} ${ln})` : "Empate";
    case "over":
      return `Más de ${ln}`;
    case "under":
      return `Menos de ${ln}`;
    case "yes":
      return "Sí";
    case "no":
      return "No";
    case "1x":
      return `${home} o empate`;
    case "x2":
      return `Empate o ${away}`;
    case "12":
      return `${home} o ${away}`;
    default:
      return ln ? `${selection} ${ln}` : selection;
  }
}

export function betLabel(market: string, selection: string, line: number | null, t: Teams = {}): string {
  return `${marketName(market, t)}: ${selectionText(market, selection, line, t)}`;
}

export const BOOKMAKERS: Record<string, string> = {
  betano: "Betano",
  bet365: "bet365",
  pinnacle: "Pinnacle",
  betfair_ex: "Betfair",
};

export function bookmakerName(b: string | null | undefined): string {
  if (!b) return "—";
  return BOOKMAKERS[b] ?? b;
}

/** Referencia del CLV: «Pinnacle, 14 min antes», «Pinnacle, 27 h antes» o «cierre de bet365» */
export function clvRefText(ref: ClvRef | null | undefined): string {
  if (!ref) return "";
  if (ref.kind === "closing") return `cierre de ${bookmakerName(ref.book)}`;
  const m = ref.minutes_before;
  return `${bookmakerName(ref.book)}, ${m < 90 ? `${m} min` : `${Math.round(m / 60)} h`} antes`;
}

// --------------------------------------------------------------------------- formulario

export type SelectionKind = "1x2" | "dc" | "ha" | "yn" | "ou";

export interface MarketOption {
  value: string;
  label: string;
  group: string;
  sel: SelectionKind;
  line?: number; // línea por defecto si el mercado la necesita
  scope?: boolean; // admite total / local / visitante
  player?: boolean;
}

export const MARKET_OPTIONS: MarketOption[] = [
  { value: "1x2", label: "Resultado (1X2)", group: "Resultado", sel: "1x2" },
  { value: "dc", label: "Doble oportunidad", group: "Resultado", sel: "dc" },
  { value: "dnb", label: "Empate no válido", group: "Resultado", sel: "ha" },
  { value: "ou_goals", label: "Goles: más/menos", group: "Goles", sel: "ou", line: 2.5, scope: true },
  { value: "btts", label: "Ambos marcan", group: "Goles", sel: "yn" },
  { value: "eh", label: "Hándicap normal (3 vías)", group: "Hándicap", sel: "1x2", line: -1 },
  { value: "ah", label: "Hándicap asiático", group: "Hándicap", sel: "ha", line: -0.5 },
  { value: "ou_corners", label: "Córners: más/menos", group: "Estadísticas", sel: "ou", line: 9.5, scope: true },
  { value: "ou_cards", label: "Tarjetas: más/menos", group: "Estadísticas", sel: "ou", line: 4.5, scope: true },
  { value: "ou_shots", label: "Remates: más/menos", group: "Estadísticas", sel: "ou", line: 24.5, scope: true },
  { value: "ou_sot", label: "Remates a puerta: más/menos", group: "Estadísticas", sel: "ou", line: 8.5, scope: true },
  { value: "ou_fouls", label: "Faltas: más/menos", group: "Estadísticas", sel: "ou", line: 22.5, scope: true },
  { value: "ou_offsides", label: "Offsides: más/menos", group: "Estadísticas", sel: "ou", line: 3.5, scope: true },
  { value: "ah_corners", label: "Hándicap de córners", group: "Estadísticas", sel: "ha", line: -1.5 },
  { value: "ah_cards", label: "Hándicap de tarjetas", group: "Estadísticas", sel: "ha", line: -0.5 },
  { value: "1x2_corners", label: "Más córners (1X2)", group: "Estadísticas", sel: "1x2" },
  { value: "player_shots", label: "Remates del jugador", group: "Jugador", sel: "ou", line: 0.5, player: true },
  { value: "player_sot", label: "Remates a puerta del jugador", group: "Jugador", sel: "ou", line: 0.5, player: true },
  { value: "player_fouls", label: "Faltas del jugador", group: "Jugador", sel: "ou", line: 0.5, player: true },
  { value: "player_goal", label: "Gol del jugador", group: "Jugador", sel: "yn", player: true },
  { value: "player_assist", label: "Asistencia del jugador", group: "Jugador", sel: "yn", player: true },
  { value: "player_goal_assist", label: "Gol o asistencia del jugador", group: "Jugador", sel: "yn", player: true },
  { value: "player_card", label: "Tarjeta al jugador", group: "Jugador", sel: "yn", player: true },
];

export function selectionsFor(kind: SelectionKind, t: Teams = {}): { value: string; label: string }[] {
  const home = t.home ?? "Local";
  const away = t.away ?? "Visitante";
  switch (kind) {
    case "1x2":
      return [
        { value: "home", label: home },
        { value: "draw", label: "Empate" },
        { value: "away", label: away },
      ];
    case "dc":
      return [
        { value: "1x", label: `${home} o empate` },
        { value: "x2", label: `Empate o ${away}` },
        { value: "12", label: `${home} o ${away}` },
      ];
    case "ha":
      return [
        { value: "home", label: home },
        { value: "away", label: away },
      ];
    case "yn":
      return [
        { value: "yes", label: "Sí" },
        { value: "no", label: "No" },
      ];
    case "ou":
      return [
        { value: "over", label: "Más de" },
        { value: "under", label: "Menos de" },
      ];
  }
}
