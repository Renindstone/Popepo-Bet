"use client";

import { useSyncExternalStore } from "react";
import { todayLima } from "./format";

const noop = () => () => {};

/** Fecha de hoy en Lima (YYYY-MM-DD). Vacía durante el prerenderizado. */
export function useToday(): string {
  return useSyncExternalStore(noop, todayLima, () => "");
}

// --------------------------------------------------------------------------- opciones que se recuerdan

const choiceListeners = new Set<() => void>();
const choiceMemory = new Map<string, string>();

function subscribeChoice(listener: () => void): () => void {
  choiceListeners.add(listener);
  return () => choiceListeners.delete(listener);
}

function readChoice(key: string): string | null {
  try {
    const stored = window.localStorage.getItem(key);
    if (stored != null) return stored;
  } catch {
    // Sin localStorage (modo privado): vale lo elegido mientras la página siga abierta
  }
  return choiceMemory.get(key) ?? null;
}

/** Una opción de la vista (como el orden de una lista) que se recuerda en este navegador; por defecto, la primera. */
export function useRemembered<T extends string>(key: string, options: readonly T[]): [T, (value: T) => void] {
  const stored = useSyncExternalStore(subscribeChoice, () => readChoice(key), () => null);
  const value = options.includes(stored as T) ? (stored as T) : options[0];
  function set(next: T) {
    choiceMemory.set(key, next);
    try {
      window.localStorage.setItem(key, next);
    } catch {
      // Se queda en memoria
    }
    choiceListeners.forEach((l) => l());
  }
  return [value, set];
}
