"use client";

import { useSyncExternalStore } from "react";
import { todayLima } from "./format";

const noop = () => () => {};

/** Fecha de hoy en Lima (YYYY-MM-DD). Vacía durante el prerenderizado. */
export function useToday(): string {
  return useSyncExternalStore(noop, todayLima, () => "");
}
