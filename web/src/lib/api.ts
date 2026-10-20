"use client";

import useSWR, { type SWRConfiguration } from "swr";

// Desde la propia máquina la API no pide clave. Con clave (otra máquina, túnel) se envía X-API-Key.
export const DIRECT_API_URL = "http://127.0.0.1:8000";
const LOCAL_HOSTS = ["localhost", "127.0.0.1", "[::1]"];

/**
 * Dirección de la API. En esta máquina el navegador la llama directamente; si el panel se abre por un túnel
 * (cloudflared, ngrok) o desde otro equipo, la pide al propio panel en /api, que la reenvía (src/proxy.ts).
 */
export function apiUrl(): string {
  const fixed = process.env.NEXT_PUBLIC_API_URL;
  if (fixed) return fixed.replace(/\/$/, "");
  if (typeof window !== "undefined" && !LOCAL_HOSTS.includes(window.location.hostname)) return "/api";
  return DIRECT_API_URL;
}

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
  // Los formularios con archivos (FormData) llevan su propio Content-Type con el separador
  if (typeof init?.body === "string") headers.set("Content-Type", "application/json");

  let res: Response;
  try {
    res = await fetch(`${apiUrl()}${path}`, { ...init, headers });
  } catch {
    throw new ApiError(
      0,
      `No hay conexión con la API en ${apiUrl()}. Arráncala con .venv/bin/apuestas api y vuelve a intentarlo.`,
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
      throw new ApiError(
        401,
        detail === "Clave inválida"
          ? "La clave guardada no es válida. Revisa que la copiaste completa."
          : "Para usar el panel desde aquí hace falta una clave de acceso.",
      );
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

export function put<T>(path: string, body: unknown): Promise<T> {
  return api<T>(path, { method: "PUT", body: JSON.stringify(body) });
}

export function del<T>(path: string): Promise<T> {
  return api<T>(path, { method: "DELETE" });
}

/** Sube un formulario con archivos (multipart). */
export function upload<T>(path: string, form: FormData): Promise<T> {
  return api<T>(path, { method: "POST", body: form });
}

/** Descarga un archivo protegido por la clave y lo deja como URL local (para <img>). */
export async function blobUrl(path: string): Promise<string> {
  const headers = new Headers();
  const key = getApiKey();
  if (key) headers.set("X-API-Key", key);
  const res = await fetch(`${apiUrl()}${path}`, { headers });
  if (!res.ok) throw new ApiError(res.status, `No se pudo cargar la imagen (${res.status}).`);
  return URL.createObjectURL(await res.blob());
}

export function useApi<T>(path: string | null, config?: SWRConfiguration<T, ApiError>) {
  return useSWR<T, ApiError>(path, (p: string) => api<T>(p), {
    revalidateOnFocus: false,
    shouldRetryOnError: false,
    ...config,
  });
}
