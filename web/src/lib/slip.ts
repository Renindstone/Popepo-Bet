"use client";

import { useSyncExternalStore } from "react";

// Cupón de Evaluar cuota: selecciones que el usuario va añadiendo, de uno o varios partidos. Se guarda en este
// navegador para no perderlo al cambiar de página.

export interface SlipLeg {
  id: string;
  matchId: string;
  match: string;
  home: string;
  away: string;
  kickoff: string;
  market: string;
  selection: string;
  /** Como la guarda la API (en el hándicap 3 vías, la del local) */
  line: number | null;
  player: string | null;
  odds: number;
  label: string;
}

export interface Slip {
  legs: SlipLeg[];
  /** Cuota del Bet Builder de cada partido, tal como la escribe el usuario */
  blockOdds: Record<string, string>;
  totalOdds: string;
  bookmaker: string;
}

const KEY = "apuestas.cupon";
const EMPTY: Slip = { legs: [], blockOdds: {}, totalOdds: "", bookmaker: "betano" };
const listeners = new Set<() => void>();
let cache: Slip | null = null;

export function getSlip(): Slip {
  if (cache) return cache;
  try {
    const raw = window.localStorage.getItem(KEY);
    cache = raw ? { ...EMPTY, ...(JSON.parse(raw) as Partial<Slip>) } : EMPTY;
  } catch {
    cache = EMPTY;
  }
  return cache;
}

export function updateSlip(change: (s: Slip) => Slip): void {
  cache = change(getSlip());
  try {
    if (cache.legs.length) window.localStorage.setItem(KEY, JSON.stringify(cache));
    else window.localStorage.removeItem(KEY);
  } catch {
    // Sin localStorage el cupón dura mientras la página siga abierta
  }
  listeners.forEach((l) => l());
}

function subscribe(listener: () => void): () => void {
  listeners.add(listener);
  return () => listeners.delete(listener);
}

export function useSlip(): Slip {
  return useSyncExternalStore(subscribe, getSlip, () => EMPTY);
}

export function addLeg(leg: Omit<SlipLeg, "id">): void {
  updateSlip((s) => ({ ...s, legs: [...s.legs, { ...leg, id: `${Date.now()}-${Math.random().toString(36).slice(2, 7)}` }] }));
}

export function removeLeg(id: string): void {
  updateSlip((s) => {
    const legs = s.legs.filter((l) => l.id !== id);
    const blockOdds = Object.fromEntries(Object.entries(s.blockOdds).filter(([m]) => legs.some((l) => l.matchId === m)));
    return { ...s, legs, blockOdds };
  });
}

export function clearSlip(): void {
  updateSlip(() => EMPTY);
}

/** Selecciones agrupadas por partido, en el orden en que se añadieron */
export function slipBlocks(slip: Slip): { matchId: string; legs: SlipLeg[] }[] {
  const order: string[] = [];
  const by = new Map<string, SlipLeg[]>();
  for (const l of slip.legs) {
    if (!by.has(l.matchId)) order.push(l.matchId);
    by.set(l.matchId, [...(by.get(l.matchId) ?? []), l]);
  }
  return order.map((matchId) => ({ matchId, legs: by.get(matchId) ?? [] }));
}

export function parseOdds(text: string | undefined): number | null {
  const n = Number((text ?? "").replace(",", "."));
  return Number.isFinite(n) && n > 1 ? n : null;
}

export function product(values: number[]): number {
  return Math.round(values.reduce((a, b) => a * b, 1) * 100) / 100;
}
