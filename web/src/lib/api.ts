"use client";

import useSWR, { type SWRConfiguration } from "swr";

// Desde la propia máquina la API no pide clave. Con clave (otra máquina, túnel) se envía X-API-Key.
export const API_URL = (process.env.NEXT_PUBLIC_API_URL ?? "http://127.0.0.1:8000").replace(/\/$/, "");

const KEY_STORAGE = "apuestas.apiKey";

export function getApiKey(): string {
  try {
    const stored = window.localStorage.getItem(KEY_STORAGE);
    if (stored) return stored;
  } catch {
    // Sin acceso a localStorage (modo privado): se usa la variable de entorno
  }
  return process.env.NEXT_PUBLIC_API_KEY ?? "";
}

export function setApiKey(key: string): void {
  try {
    if (key) window.localStorage.setItem(KEY_STORAGE, key);
    else window.localStorage.removeItem(KEY_STORAGE);
  } catch {
    // Ignorado: la clave solo dura la sesión
  }
}

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

function detailText(detail: unknown): string | null {
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    // Errores de validación de FastAPI (422)
    return detail
      .map((d) => (typeof d === "object" && d && "msg" in d ? String((d as { msg: unknown }).msg) : String(d)))
      .join("; ");
  }
  return null;
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  const headers = new Headers(init?.headers);
  const key = getApiKey();
  if (key) headers.set("X-API-Key", key);
  if (init?.body) headers.set("Content-Type", "application/json");

  let res: Response;
  try {
    res = await fetch(`${API_URL}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      0,
      `No hay conexión con la API en ${API_URL}. Arráncala con .venv/bin/apuestas api y vuelve a intentarlo.`,
    );
  }
  if (!res.ok) {
    let detail: string | null = null;
    try {
      detail = detailText((await res.json()).detail);
    } catch {
      // Respuesta sin JSON
    }
    if (res.status === 401) {
      throw new ApiError(401, detail ?? "La API pide una clave. Escríbela en Estado de los datos → Conexión.");
    }
    if (res.status === 503) {
      throw new ApiError(503, detail ?? "Los modelos aún no están entrenados. Ejecuta .venv/bin/apuestas train.");
    }
    throw new ApiError(res.status, detail ?? `La API respondió con un error ${res.status}.`);
  }
  return res.json() as Promise<T>;
}

export function post<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: "POST", body: JSON.stringify(body) });
}

export function useApi<T>(path: string | null, config?: SWRConfiguration<T, ApiError>) {
  return useSWR<T, ApiError>(path, (p: string) => api<T>(p), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
    ...config,
  });
}
