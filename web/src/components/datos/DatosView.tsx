"use client";

import { useEffect, useRef, useState, useSyncExternalStore } from "react";
import { ApiKeyForm, Button, ErrorNote, Figure, Loading, PageTitle, Section, Tag } from "@/components/ui";
import { type ApiError, apiUrl, DIRECT_API_URL, post, put, useApi } from "@/lib/api";
import { ago, dateTimeLima, int, pct, shortDate, todayLima } from "@/lib/format";
import { tr } from "@/lib/i18n";
import { useMe } from "@/lib/me";
import type { DataStatus, Me, SyncStatus } from "@/lib/types";

const sources = (): Record<string, { name: string; what: string }> => ({
  fdco: {
    name: "football-data.co.uk",
    what: tr("Resultados, estadísticas y cuotas de bet365, Pinnacle y Betfair", "Results, stats and odds from bet365, Pinnacle and Betfair"),
  },
  fotmob: {
    name: "FotMob",
    what: tr(
      "Alineaciones, lesiones, sanciones, árbitros y estadísticas de jugadores",
      "Line-ups, injuries, suspensions, referees and player stats",
    ),
  },
  understat: { name: "Understat", what: tr("Segundo modelo de xG", "Second xG model") },
  oddspapi: { name: "OddsPapi", what: tr("Cuotas de Betano (opcional, experimental)", "Betano odds (optional, experimental)") },
  dedupe: {
    name: tr("Equipos duplicados", "Duplicate teams"),
    what: tr(
      "Une el mismo equipo escrito distinto en cada fuente (cada día a las 05:30)",
      "Merges the same team spelt differently in each source (every day at 05:30)",
    ),
  },
});

const STALE_HOURS = 48;

function statusTag(status: string, finishedAt: string | null) {
  if (status === "running") return <Tag tone="tarjeta">{tr("En curso", "Running")}</Tag>;
  if (status !== "ok") return <Tag tone="rojo">{tr("Falló", "Failed")}</Tag>;
  const hours = finishedAt ? (Date.now() - new Date(finishedAt).getTime()) / 3.6e6 : Infinity;
  if (hours > STALE_HOURS) return <Tag tone="tarjeta">{tr("Desactualizada", "Out of date")}</Tag>;
  return <Tag tone="boli">{tr("Al día", "Up to date")}</Tag>;
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
      ? {
          text: tr(
            `Paso ${(sync?.done_steps ?? 0) + 1} de ${sync?.total_steps}: ${sync?.step ?? ""}`,
            `Step ${(sync?.done_steps ?? 0) + 1} of ${sync?.total_steps}: ${sync?.step ?? ""}`,
          ),
          tone: "text-grafito",
        }
      : sync?.error
        ? { text: sync.error, tone: "text-rojo" }
        : sync?.finished_at
          ? {
              text: tr(
                `Sincronizado ${ago(sync.finished_at)}${waiting ? `; puedes volver a hacerlo ${ago(sync.next_allowed_at)}` : ""}.`,
                `Synced ${ago(sync.finished_at)}${waiting ? `; you can do it again ${ago(sync.next_allowed_at)}` : ""}.`,
              ),
              tone: "text-grafito",
            }
          : null;

  return (
    <div className="flex flex-col items-start gap-1 sm:items-end">
      <Button onClick={start} disabled={running || starting || waiting}>
        <RefreshIcon spinning={running || starting} />
        {running ? tr("Sincronizando…", "Syncing…") : tr("Sincronizar", "Sync")}
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
  const SOURCES = sources();

  // Al terminar la sincronización se recarga la tabla de fuentes
  const wasSyncing = useRef(false);
  const reloadStatus = status.mutate;
  useEffect(() => {
    if (wasSyncing.current && !syncing) void reloadStatus();
    wasSyncing.current = syncing;
  }, [syncing, reloadStatus]);

  return (
    <>
      <PageTitle
        title={tr("Estado de los datos", "Data status")}
        sub={tr(
          "Cuándo se actualizó cada fuente y con qué datos trabaja el modelo. Se refresca cada minuto.",
          "When each source was last updated and what data the model works with. It refreshes every minute.",
        )}
      />
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
            title={tr("Fuentes", "Sources")}
            intro={tr(
              "Última tarea registrada de cada fuente. Ninguna fuente puede tumbar la ingesta: si una falla, las demás siguen. «Sincronizar» descarga ahora lo de las 05:30 y las 08:30 de FotMob, football-data y Understat y reentrena el modelo (tarda unos minutos y no gasta peticiones de OddsPapi).",
              "Latest recorded task for each source. No source can bring the ingestion down: if one fails, the others carry on. “Sync” downloads now the 05:30 and 08:30 runs from FotMob, football-data and Understat and retrains the model (it takes a few minutes and spends no OddsPapi requests).",
            )}
            actions={<SyncButton sync={sync.data} onChange={(st) => sync.mutate(st, { revalidate: false })} />}
          >
            <div className="overflow-x-auto">
              <table className="w-full min-w-[680px] border-collapse text-interfaz">
                <thead>
                  <tr className="border-b border-regla text-left text-nota text-grafito">
                    <th className="py-2 pr-4 font-medium">{tr("Fuente", "Source")}</th>
                    <th className="py-2 pr-4 font-medium">{tr("Última tarea", "Latest task")}</th>
                    <th className="py-2 pr-4 font-medium">{tr("Estado", "Status")}</th>
                    <th className="py-2 font-medium">{tr("Terminó", "Finished")}</th>
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
                          <span className="text-grafito">{tr("Aún no termina", "Not finished yet")}</span>
                        )}
                        {src.status !== "ok" && src.last_ok && (
                          <span className="mt-1 block text-nota text-grafito">
                            {tr("Último dato bueno:", "Last good data:")} {dateTimeLima(src.last_ok)} ({ago(src.last_ok)})
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
                {tr(
                  "Sin cuotas de Betano automáticas: OddsPapi no está configurado. Usa Evaluar cuota con la cuota que ves en la app de Betano.",
                  "No automatic Betano odds: OddsPapi is not set up. Use Check odds with the odds you see in the Betano app.",
                )}
              </p>
            )}
          </Section>

          <Section title={tr("Modelo y base de datos", "Model and database")}>
            <div className="grid grid-cols-2 gap-x-8 gap-y-6 sm:grid-cols-3 lg:grid-cols-6">
              <Modelo asOf={s.model_as_of} />
              <Figure value={int(s.counts.matches)} label={tr("partidos", "matches")} />
              <Figure
                value={int(s.counts.matches_with_details)}
                label={tr(
                  `con estadísticas detalladas (${pct(s.counts.matches_with_details / Math.max(1, s.counts.matches))})`,
                  `with detailed stats (${pct(s.counts.matches_with_details / Math.max(1, s.counts.matches))})`,
                )}
              />
              <Figure value={int(s.counts.players)} label={tr("jugadores", "players")} />
              <Figure value={int(s.counts.active_absences)} label={tr("bajas activas", "current absences")} />
              <Figure value={int(s.counts.odds_rows)} label={tr("cuotas guardadas", "odds saved")} />
            </div>
          </Section>
        </>
      )}
      <Conexion />
      <Inteligencia />
    </>
  );
}

/** Interruptor de la IA de este usuario: capturas y explicaciones de Claude */
function Inteligencia() {
  const { me, mutate } = useMe();
  const [state, setState] = useState<{ busy: boolean; error?: ApiError }>({ busy: false });
  async function set(on: boolean) {
    setState({ busy: true });
    try {
      await mutate(await put<Me>("/me", { ai_enabled: on }), { revalidate: false });
      setState({ busy: false });
    } catch (e) {
      setState({ busy: false, error: e as ApiError });
    }
  }
  const option = (on: boolean, label: string) => {
    const active = me?.ai_enabled === on;
    return (
      <button
        type="button"
        aria-pressed={active}
        disabled={!me || state.busy}
        onClick={() => set(on)}
        className={`h-10 border px-4 text-interfaz font-bold transition-colors disabled:opacity-60 ${
          active ? "border-tinta bg-tinta text-papel" : "border-tinta bg-hoja text-tinta hover:bg-tinta hover:text-papel"
        }`}
      >
        {label}
      </button>
    );
  };
  return (
    <Section
      id="ia"
      title={tr("Inteligencia artificial", "Artificial intelligence")}
      intro={tr(
        "Cada usuario decide si usa la IA en el panel. Los números del modelo no cambian: la IA nunca los calcula.",
        "Each user decides whether to use AI in the panel. The model's numbers do not change: the AI never calculates them.",
      )}
    >
      <div className="flex flex-wrap items-center gap-x-6 gap-y-3">
        <p className="text-interfaz font-bold">{tr("Usar IA en el panel", "Use AI in the panel")}</p>
        <div role="group" aria-label={tr("Usar IA en el panel", "Use AI in the panel")} className="flex">
          {option(true, tr("Encendida", "On"))}
          {option(false, tr("Apagada", "Off"))}
        </div>
      </div>
      {state.error && <ErrorNote error={state.error} />}
      <p className="mt-4 text-interfaz">{tr("Si la apagas:", "If you turn it off:")}</p>
      <ul className="mt-1 max-w-[72ch] list-disc space-y-1 pl-5 text-interfaz text-grafito">
        <li>{tr("desaparecen «Capturas» del menú y «¿Viste una cuota?» de Hoy;", "“Screenshots” disappears from the menu and “Spotted some odds?” from Today;")}</li>
        <li>
          {tr(
            "«Por qué falló» y «Sorpresas» muestran solo los números, sin la explicación de Claude;",
            "“Why it lost” and “Surprises” show only the numbers, without Claude's explanation;",
          )}
        </li>
        <li>{tr("no se procesan tus capturas pendientes.", "your pending screenshots are not processed.")}</li>
      </ul>
    </Section>
  );
}

function Modelo({ asOf }: { asOf: string | null }) {
  if (!asOf) return <Figure value={tr("Sin entrenar", "Not trained")} label={tr("ejecuta apuestas train", "run apuestas train")} tone="rojo" />;
  const days = daysSince(asOf);
  return (
    <Figure
      value={shortDate(asOf)}
      label={
        days <= 0
          ? tr("modelo entrenado hoy", "model trained today")
          : tr(`modelo entrenado hace ${days} ${days === 1 ? "día" : "días"}`, `model trained ${days} ${days === 1 ? "day" : "days"} ago`)
      }
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
      title={tr("Conexión", "Connection")}
      intro={tr(
        "Desde esta misma máquina la API no pide clave. Si abres el panel desde otro equipo, escribe tu clave (apuestas user create-key). Se guarda solo en este navegador.",
        "From this same machine the API asks for no key. If you open the panel from another computer, type your key (apuestas user create-key). It is only saved in this browser.",
      )}
    >
      <dl className="mb-5 grid max-w-xl grid-cols-[auto_1fr] gap-x-6 gap-y-1.5 text-interfaz">
        <dt className="text-grafito">API</dt>
        <dd className="num font-semibold break-all">{url}</dd>
        <dt className="text-grafito">{tr("Estado", "Status")}</dt>
        <dd>
          {health.error ? (
            <Tag tone="rojo">{tr("Sin conexión", "No connection")}</Tag>
          ) : health.data ? (
            <Tag tone="boli">{tr(`Conectada, versión ${health.data.version}`, `Connected, version ${health.data.version}`)}</Tag>
          ) : (
            <span className="text-grafito">{tr("Comprobando…", "Checking…")}</span>
          )}
        </dd>
      </dl>
      <ApiKeyForm label={tr("Clave de la API (opcional)", "API key (optional)")} />
    </Section>
  );
}
