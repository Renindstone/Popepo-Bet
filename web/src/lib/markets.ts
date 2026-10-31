// Mercados: nombres en español e inglés (los de Betano en cada idioma) y opciones del formulario de evaluación

import { lineText } from "./format";
import { tr } from "./i18n";
import type { ClvRef } from "./types";

type Pair = [string, string];

const STATS: Record<string, Pair> = {
  goals: ["Goles", "Goals"],
  shots: ["Remates", "Shots"],
  sot: ["Remates a puerta", "Shots on target"],
  shots_on_target: ["Remates a puerta", "Shots on target"],
  corners: ["Córners", "Corners"],
  cards: ["Tarjetas", "Cards"],
  fouls: ["Faltas", "Fouls"],
  offsides: ["Offsides", "Offsides"],
};

const PLAYER: Record<string, Pair> = {
  player_shots: ["Remates de", "Shots by"],
  player_sot: ["Remates a puerta de", "Shots on target by"],
  player_fouls: ["Faltas de", "Fouls by"],
  player_goal: ["Gol de", "Goal by"],
  player_assist: ["Asistencia de", "Assist by"],
  player_goal_assist: ["Gol o asistencia de", "Goal or assist by"],
  player_card: ["Tarjeta para", "Card for"],
};

const BASE: Record<string, Pair> = {
  combo: ["Combinada", "Accumulator"],
  "1x2": ["Resultado", "Match Result"],
  dc: ["Doble oportunidad", "Double Chance"],
  dnb: ["Empate no válido", "Draw No Bet"],
  btts: ["Ambos marcan", "Both Teams To Score"],
  ah: ["Hándicap asiático", "Asian Handicap"],
  eh: ["Hándicap (3 vías)", "Handicap (3-way)"],
};

/** Nombre de una estadística: "corners" → "Córners" ("Corners") */
export function statName(stat: string): string {
  return STATS[stat] ? tr(...STATS[stat]) : stat;
}

export interface Teams {
  home?: string;
  away?: string;
  player?: string | null;
}

export function marketName(market: string, t: Teams = {}): string {
  if (BASE[market]) return tr(...BASE[market]);
  if (market.startsWith("player_")) {
    return `${PLAYER[market] ? tr(...PLAYER[market]) : market} ${t.player ?? tr("jugador", "player")}`;
  }
  let rest = market;
  let scope: "home" | "away" | null = null;
  for (const sc of ["home", "away"] as const) {
    if (rest.endsWith(`_${sc}`)) {
      rest = rest.slice(0, -sc.length - 1);
      scope = sc;
    }
  }
  const [kind, ...statParts] = rest.split("_");
  const stat = statName(statParts.join("_"));
  const team =
    scope === "home" ? t.home ?? tr("local", "home team") : scope === "away" ? t.away ?? tr("visitante", "away team") : null;
  if (kind === "ou") return team ? tr(`${stat} de ${team}`, `${team} ${stat.toLowerCase()}`) : stat;
  if (kind === "ah") return tr(`Hándicap de ${stat.toLowerCase()}`, `${stat} Handicap`);
  if (kind === "1x2") return tr(`Más ${stat.toLowerCase()}`, `Most ${stat.toLowerCase()}`);
  return market;
}

export function selectionText(market: string, selection: string, line: number | null, t: Teams = {}): string {
  const home = t.home ?? tr("Local", "Home");
  const away = t.away ?? tr("Visitante", "Away");
  const ln = lineText(market, line);
  // Hándicap 3 vías: la línea se guarda como la del local; al visitante se le muestra la suya ("Coventry +2")
  const awayLn = market === "eh" && line != null ? lineText(market, -line) : ln;
  switch (selection) {
    case "home":
      return ln ? `${home} ${ln}` : home;
    case "away":
      return awayLn ? `${away} ${awayLn}` : away;
    case "draw":
      return market === "eh" && ln ? tr(`Empate (${home} ${ln})`, `Draw (${home} ${ln})`) : tr("Empate", "Draw");
    case "over":
      return tr(`Más de ${ln}`, `Over ${ln}`);
    case "under":
      return tr(`Menos de ${ln}`, `Under ${ln}`);
    case "yes":
      return tr("Sí", "Yes");
    case "no":
      return "No";
    case "1x":
      return tr(`${home} o empate`, `${home} or Draw`);
    case "x2":
      return tr(`Empate o ${away}`, `Draw or ${away}`);
    case "12":
      return tr(`${home} o ${away}`, `${home} or ${away}`);
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
  if (ref.kind === "closing") return tr(`cierre de ${bookmakerName(ref.book)}`, `${bookmakerName(ref.book)} closing line`);
  const m = ref.minutes_before;
  const ago = m < 90 ? `${m} min` : `${Math.round(m / 60)} h`;
  return tr(`${bookmakerName(ref.book)}, ${ago} antes`, `${bookmakerName(ref.book)}, ${ago} before`);
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

/** Opciones del formulario, en el idioma en uso */
export function marketOptions(): MarketOption[] {
  const result = tr("Resultado", "Result");
  const goals = tr("Goles", "Goals");
  const handicap = tr("Hándicap", "Handicap");
  const stats = tr("Estadísticas", "Stats");
  const player = tr("Jugador", "Player");
  return [
    { value: "1x2", label: tr("Resultado (1X2)", "Match Result (1X2)"), group: result, sel: "1x2" },
    { value: "dc", label: tr("Doble oportunidad", "Double Chance"), group: result, sel: "dc" },
    { value: "dnb", label: tr("Empate no válido", "Draw No Bet"), group: result, sel: "ha" },
    { value: "ou_goals", label: tr("Goles: más/menos", "Goals: Over/Under"), group: goals, sel: "ou", line: 2.5, scope: true },
    { value: "btts", label: tr("Ambos marcan", "Both Teams To Score"), group: goals, sel: "yn" },
    { value: "eh", label: tr("Hándicap normal (3 vías)", "Handicap (3-way)"), group: handicap, sel: "1x2", line: -1 },
    { value: "ah", label: tr("Hándicap asiático", "Asian Handicap"), group: handicap, sel: "ha", line: -0.5 },
    { value: "ou_corners", label: tr("Córners: más/menos", "Corners: Over/Under"), group: stats, sel: "ou", line: 9.5, scope: true },
    { value: "ou_cards", label: tr("Tarjetas: más/menos", "Cards: Over/Under"), group: stats, sel: "ou", line: 4.5, scope: true },
    { value: "ou_shots", label: tr("Remates: más/menos", "Shots: Over/Under"), group: stats, sel: "ou", line: 24.5, scope: true },
    { value: "ou_sot", label: tr("Remates a puerta: más/menos", "Shots on target: Over/Under"), group: stats, sel: "ou", line: 8.5, scope: true },
    { value: "ou_fouls", label: tr("Faltas: más/menos", "Fouls: Over/Under"), group: stats, sel: "ou", line: 22.5, scope: true },
    { value: "ou_offsides", label: tr("Offsides: más/menos", "Offsides: Over/Under"), group: stats, sel: "ou", line: 3.5, scope: true },
    { value: "ah_corners", label: tr("Hándicap de córners", "Corners Handicap"), group: stats, sel: "ha", line: -1.5 },
    { value: "ah_cards", label: tr("Hándicap de tarjetas", "Cards Handicap"), group: stats, sel: "ha", line: -0.5 },
    { value: "1x2_corners", label: tr("Más córners (1X2)", "Most Corners (1X2)"), group: stats, sel: "1x2" },
    { value: "player_shots", label: tr("Remates del jugador", "Player shots"), group: player, sel: "ou", line: 0.5, player: true },
    { value: "player_sot", label: tr("Remates a puerta del jugador", "Player shots on target"), group: player, sel: "ou", line: 0.5, player: true },
    { value: "player_fouls", label: tr("Faltas del jugador", "Player fouls"), group: player, sel: "ou", line: 0.5, player: true },
    { value: "player_goal", label: tr("Gol del jugador", "Player to score"), group: player, sel: "yn", player: true },
    { value: "player_assist", label: tr("Asistencia del jugador", "Player to assist"), group: player, sel: "yn", player: true },
    { value: "player_goal_assist", label: tr("Gol o asistencia del jugador", "Player to score or assist"), group: player, sel: "yn", player: true },
    { value: "player_card", label: tr("Tarjeta al jugador", "Player to be booked"), group: player, sel: "yn", player: true },
  ];
}

export function selectionsFor(kind: SelectionKind, t: Teams = {}): { value: string; label: string }[] {
  const home = t.home ?? tr("Local", "Home");
  const away = t.away ?? tr("Visitante", "Away");
  switch (kind) {
    case "1x2":
      return [
        { value: "home", label: home },
        { value: "draw", label: tr("Empate", "Draw") },
        { value: "away", label: away },
      ];
    case "dc":
      return [
        { value: "1x", label: tr(`${home} o empate`, `${home} or Draw`) },
        { value: "x2", label: tr(`Empate o ${away}`, `Draw or ${away}`) },
        { value: "12", label: tr(`${home} o ${away}`, `${home} or ${away}`) },
      ];
    case "ha":
      return [
        { value: "home", label: home },
        { value: "away", label: away },
      ];
    case "yn":
      return [
        { value: "yes", label: tr("Sí", "Yes") },
        { value: "no", label: "No" },
      ];
    case "ou":
      return [
        { value: "over", label: tr("Más de", "Over") },
        { value: "under", label: tr("Menos de", "Under") },
      ];
  }
}
