"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ApiKeyForm, Button, ErrorNote, Figure, Loading, PageTitle, Section, Tag } from "@/components/ui";
import { type ApiError, apiUrl, DIRECT_API_URL, post, useApi } from "@/lib/api";
import { ago, dateTimeLima, int, pct, shortDate, todayLima } from "@/lib/format";
import type { DataStatus, SyncStatus } from "@/lib/types";

const SOURCES: Record<string, { name: string; what: string }> = {
  fdco: { name: "football-data.co.uk", what: "Resultados, estadísticas y cuotas de bet365, Pinnacle y Betfair" },
  fotmob: { name: "FotMob", what: "Alineaciones, lesiones, sanciones, árbitros y estadísticas de jugadores" },
  understat: { name: "Understat", what: "Segundo modelo de xG" },
  oddspapi: { name: "OddsPapi", what: "Cuotas de Betano (opcional, experimental)" },
  dedupe: {
    name: "Equipos duplicados",
    what: "Une el mismo equipo escrito distinto en cada fuente (cada día a las 05:30)",
  },
};

const STALE_HOURS = 48;

function statusTag(status: string, finishedAt: string | null) {
  if (status === "running") return <Tag tone="tarjeta">En curso</Tag>;
  if (status !== "ok") return <Tag tone="rojo">Falló</Tag>;
  const hours = finishedAt ? (Date.now() - new Date(finishedAt).getTime()) / 3.6e6 : Infinity;
  if (hours > STALE_HOURS) return <Tag tone="tarjeta">Desactualizada</Tag>;
  return <Tag tone="boli">Al día</Tag>;
}

/** Flechas en círculo: volver a descargar */
function RefreshIcon({ spinning }: { spinning: boolean }) {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 24 24"
      className={`size-4 ${spinning ? "animate-spin motion-reduce:animate-none" : ""}`}
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
      <path d="M21 12a9 9 0 1 1-9-9c2.52 0 4.93 1 6.74 2.74L21 8" />
      <path d="M21 3v5h-5" />
    </svg>
  );
}

/** Botón de Datos para forzar la sincronización de las fuentes gratuitas, con el paso en curso o el resultado. */
function SyncButton({ sync, onChange }: { sync: SyncStatus | undefined; onChange: (st: SyncStatus) => void }) {
  const [starting, setStarting] = useState(false);
  const [refused, setRefused] = useState<string | null>(null);
  const running = !!sync?.running;
  const waiting = !running && !!sync?.next_allowed_at;

  async function start() {
    setStarting(true);
    setRefused(null);
    try {
      onChange(await post<SyncStatus>("/sync", {}));
    } catch (e) {
      setRefused((e as ApiError).message);
    } finally {
      setStarting(false);
    }
  }

  const note = refused
    ? { text: refused, tone: "text-rojo" }
    : running
      ? { text: `Paso ${(sync?.done_steps ?? 0) + 1} de ${sync?.total_steps}: ${sync?.step ?? ""}`, tone: "text-grafito" }
      : sync?.error
        ? { text: sync.error, tone: "text-rojo" }
        : sync?.finished_at
          ? {
              text: `Sincronizado ${ago(sync.finished_at)}${waiting ? `; puedes volver a hacerlo ${ago(sync.next_allowed_at)}` : ""}.`,
              tone: "text-grafito",
            }
          : null;

  return (
    <div className="flex flex-col items-start gap-1 sm:items-end">
      <Button onClick={start} disabled={running || starting || waiting}>
        <RefreshIcon spinning={running || starting} />
        {running ? "Sincronizando…" : "Sincronizar"}
      </Button>
      {note && (
        <p role="status" aria-live="polite" className={`max-w-xs text-nota sm:text-right ${note.tone}`}>
          {note.text}
        </p>
      )}
    </div>
  );
}

function daysSince(day: string): number {
  const [y, m, d] = day.split("-").map(Number);
  const [ty, tm, td] = todayLima().split("-").map(Number);
  return Math.round((Date.UTC(ty, tm - 1, td) - Date.UTC(y, m - 1, d)) / 864e5);
}

export function DatosView() {
  // Mientras se sincroniza, el estado se mira cada pocos segundos; después, cada minuto
  const sync = useApi<SyncStatus>("/sync", {
    refreshInterval: (d) => (d?.running ? 3_000 : d?.next_allowed_at ? 30_000 : 0),
  });
  const syncing = !!sync.data?.running;
  const status = useApi<DataStatus>("/status", { refreshInterval: syncing ? 5_000 : 60_000 });
  const s = status.data;

  // Al terminar la sincronización se recarga la tabla de fuentes
  const wasSyncing = useRef(false);
  const reloadStatus = status.mutate;
  useEffect(() => {
    if (wasSyncing.current && !syncing) void reloadStatus();
    wasSyncing.current = syncing;
  }, [syncing, reloadStatus]);

  return (
    <>
      <PageTitle title="Estado de los datos" sub="Cuándo se actualizó cada fuente y con qué datos trabaja el modelo. Se refresca cada minuto." />
      {status.error ? (
        <div className="pb-10">
          <ErrorNote error={status.error} onRetry={() => status.mutate()} />
        </div>
      ) : !s ? (
        <div className="pb-10">
          <Loading lines={5} />
        </div>
      ) : (
        <>
          <Section
            title="Fuentes"
            intro="Última tarea registrada de cada fuente. Ninguna fuente puede tumbar la ingesta: si una falla, las demás siguen. «Sincronizar» descarga ahora lo de las 05:30 y las 08:30 de FotMob, football-data y Understat y reentrena el modelo (tarda unos minutos y no gasta peticiones de OddsPapi)."
            actions={<SyncButton sync={sync.data} onChange={(st) => sync.mutate(st, { revalidate: false })} />}
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px] border-collapse text-interfaz">
                <thead>
                  <tr className="border-b border-regla text-left text-nota text-grafito">
                    <th className="py-2 pr-4 font-medium">Fuente</th>
                    <th className="py-2 pr-4 font-medium">Última tarea</th>
                    <th className="py-2 pr-4 font-medium">Estado</th>
                    <th className="py-2 font-medium">Terminó</th>
                  </tr>
                </thead>
                <tbody>
                  {Object.entries(s.sources).map(([key, src]) => (
                    <tr key={key} className="border-b border-regla-suave align-top">
                      <td className="py-2.5 pr-4">
                        <span className="font-semibold">{SOURCES[key]?.name ?? key}</span>
                        {SOURCES[key] && <span className="block text-nota text-grafito">{SOURCES[key].what}</span>}
                      </td>
                      <td className="py-2.5 pr-4 text-grafito">{src.task}</td>
                      <td className="py-2.5 pr-4">
                        {statusTag(src.status, src.finished_at)}
                        {src.reason && <span className="mt-1 block text-nota text-grafito">{src.reason}</span>}
                      </td>
                      <td className="num py-2.5">
                        {src.finished_at ? (
                          <>
                            {dateTimeLima(src.finished_at)}
                            <span className="block text-nota text-grafito">{ago(src.finished_at)}</span>
                          </>
                        ) : (
                          <span className="text-grafito">Aún no termina</span>
                        )}
                        {src.status !== "ok" && src.last_ok && (
                          <span className="mt-1 block text-nota text-grafito">
                            Último dato bueno: {dateTimeLima(src.last_ok)} ({ago(src.last_ok)})
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            {!s.sources.oddspapi && (
              <p className="mt-3 max-w-[68ch] text-nota text-grafito">
                Sin cuotas de Betano automáticas: OddsPapi no está configurado. Usa Evaluar cuota con la cuota que ves en la
                app de Betano.
              </p>
            )}
          </Section>

          <Section title="Modelo y base de datos">
            <div className="grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-3 lg:grid-cols-6">
              <Modelo asOf={s.model_as_of} />
              <Figure value={int(s.counts.matches)} label="partidos" />
              <Figure
                value={int(s.counts.matches_with_details)}
                label={`con estadísticas detalladas (${pct(s.counts.matches_with_details / Math.max(1, s.counts.matches))})`}
              />
              <Figure value={int(s.counts.players)} label="jugadores" />
              <Figure value={int(s.counts.active_absences)} label="bajas activas" />
              <Figure value={int(s.counts.odds_rows)} label="cuotas guardadas" />
            </div>
          </Section>
        </>
      )}
      <Conexion />
    </>
  );
}

function Modelo({ asOf }: { asOf: string | null }) {
  if (!asOf) return <Figure value="Sin entrenar" label="ejecuta apuestas train" tone="rojo" />;
  const days = daysSince(asOf);
  return (
    <Figure
      value={shortDate(asOf)}
      label={days <= 0 ? "modelo entrenado hoy" : `modelo entrenado hace ${days} ${days === 1 ? "día" : "días"}`}
      tone={days > 7 ? "rojo" : undefined}
    />
  );
}

const noop = () => () => {};

function Conexion() {
  const health = useApi<{ ok: boolean; version: string }>("/health");
  const url = useSyncExternalStore(noop, apiUrl, () => DIRECT_API_URL);

  return (
    <Section
      title="Conexión"
      intro="Desde esta misma máquina la API no pide clave. Si abres el panel desde otro equipo, escribe tu clave (apuestas user create-key). Se guarda solo en este navegador."
    >
      <dl className="mb-5 grid max-w-xl grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 text-interfaz">
        <dt className="text-grafito">API</dt>
        <dd className="num font-semibold break-all">{url}</dd>
        <dt className="text-grafito">Estado</dt>
        <dd>
          {health.error ? (
            <Tag tone="rojo">Sin conexión</Tag>
          ) : health.data ? (
            <Tag tone="boli">Conectada, versión {health.data.version}</Tag>
          ) : (
            <span className="text-grafito">Comprobando…</span>
          )}
        </dd>
      </dl>
      <ApiKeyForm label="Clave de la API (opcional)" />
    </Section>
  );
}
