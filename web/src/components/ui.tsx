"use client";

import { type FormEvent, type ReactNode, useState, useSyncExternalStore } from "react";
import { type ApiError, getApiKey, setApiKey } from "@/lib/api";
import { pct } from "@/lib/format";

export function PageTitle({ title, sub, actions }: { title: string; sub?: ReactNode; actions?: ReactNode }) {
  return (
    <div className="flex flex-wrap items-end justify-between gap-x-6 gap-y-3 pb-6">
      <div className="min-w-0">
        <h1 className="cond text-[2.5rem] leading-[1.05] font-extrabold tracking-[-0.01em] sm:text-5xl">{title}</h1>
        {sub && <div className="mt-1.5 text-grafito">{sub}</div>}
      </div>
      {actions && <div className="flex flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export function Section({
  title,
  intro,
  children,
  id,
  actions,
}: {
  title: string;
  intro?: ReactNode;
  children: ReactNode;
  id?: string;
  actions?: ReactNode;
}) {
  return (
    <section id={id} className="border-t border-regla pt-5 pb-10">
      <div className="mb-4 flex flex-wrap items-baseline justify-between gap-x-6 gap-y-2">
        <h2 className="semi text-xl font-bold">{title}</h2>
        {actions}
      </div>
      {intro && <p className="-mt-2 mb-4 max-w-[68ch] text-[0.95rem] text-grafito">{intro}</p>}
      {children}
    </section>
  );
}

export function Loading({ lines = 3, label = "Cargando…" }: { lines?: number; label?: string }) {
  return (
    <div role="status" aria-live="polite" className="space-y-2.5 py-2">
      <span className="sr-only">{label}</span>
      {Array.from({ length: lines }, (_, i) => (
        <div key={i} className="esqueleto h-4 rounded-sm" style={{ width: `${92 - i * 17}%` }} />
      ))}
    </div>
  );
}

export function ErrorNote({ error, onRetry }: { error: ApiError | Error; onRetry?: () => void }) {
  // Reintentar solo tiene sentido si la API no respondió o falló; un 404 o un 400 no cambian
  const status = "status" in error ? error.status : 0;
  const retryable = status === 0 || status >= 500;
  if (status === 401) {
    return (
      <div role="alert" className="max-w-[68ch] border-l-[3px] border-boli bg-boli-suave/60 px-4 py-3">
        <p className="font-semibold">{error.message}</p>
        <p className="mt-0.5 mb-3 text-[0.95rem]">Escribe la clave que te pasaron. Se guarda solo en este navegador.</p>
        <ApiKeyForm onSaved={() => window.location.reload()} />
      </div>
    );
  }
  return (
    <div role="alert" className="max-w-[68ch] border-l-[3px] border-rojo bg-rojo-suave/60 px-4 py-3">
      <p className="font-semibold">No se pudo cargar</p>
      <p className="mt-0.5 text-[0.95rem]">{error.message}</p>
      {onRetry && retryable && (
        <button type="button" onClick={onRetry} className="mt-2 text-[0.95rem] font-semibold text-boli underline underline-offset-4">
          Reintentar
        </button>
      )}
    </div>
  );
}

const noop = () => () => {};

/** Clave de acceso a la API, guardada en este navegador (para usar el panel desde otro equipo). */
export function ApiKeyForm({ label = "Clave de acceso", onSaved }: { label?: string; onSaved?: (key: string) => void }) {
  const stored = useSyncExternalStore(noop, getApiKey, () => "");
  const [key, setKey] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);
  const value = key ?? stored;

  function save(e: FormEvent) {
    e.preventDefault();
    setApiKey(value.trim());
    setSaved(true);
    onSaved?.(value.trim());
  }

  return (
    <>
      <form onSubmit={save} className="flex max-w-xl flex-wrap items-end gap-3">
        <div className="min-w-0 flex-1">
          <label htmlFor="clave" className="mb-1 block text-[0.9rem] font-semibold">
            {label}
          </label>
          <input
            id="clave"
            type="password"
            autoComplete="off"
            value={value}
            onChange={(e) => {
              setKey(e.target.value);
              setSaved(false);
            }}
            placeholder="apk_…"
            className="h-11 w-full rounded-[3px] border border-regla bg-hoja px-3 text-tinta focus:border-boli"
          />
        </div>
        <Button type="submit">Guardar clave</Button>
      </form>
      {saved && <p className="mt-2 text-[0.9rem] text-grafito">{value.trim() ? "Clave guardada." : "Clave borrada."}</p>}
    </>
  );
}

export function Empty({ children }: { children: ReactNode }) {
  return <div className="max-w-[68ch] py-2 text-grafito">{children}</div>;
}

type Tone = "neutral" | "boli" | "rojo" | "tarjeta" | "confirmada";

const TONES: Record<Tone, string> = {
  neutral: "border-regla text-grafito",
  boli: "border-boli/40 bg-boli-suave text-boli",
  rojo: "border-rojo/40 bg-rojo-suave text-rojo",
  tarjeta: "border-tarjeta/50 bg-tarjeta-suave text-tinta",
  // Alineación confirmada: relleno azul claro que se distingue de un vistazo (igual en tema claro y oscuro)
  confirmada: "border-[#93c5fd] bg-[#dbeafe] text-[#1e3a8a] font-semibold",
};

export function Tag({ tone = "neutral", className = "", children }: { tone?: Tone; className?: string; children: ReactNode }) {
  return (
    <span className={`inline-flex items-center rounded-sm border px-1.5 py-px text-[0.8rem] leading-5 font-medium whitespace-nowrap ${TONES[tone]} ${className}`}>
      {children}
    </span>
  );
}

/** Cifra destacada con su explicación debajo */
export function Figure({
  value,
  label,
  tone,
  size = "md",
}: {
  value: ReactNode;
  label: ReactNode;
  tone?: "boli" | "rojo" | "tarjeta";
  size?: "md" | "lg";
}) {
  const color = tone === "boli" ? "text-boli" : tone === "rojo" ? "text-rojo" : "";
  return (
    <div className="min-w-0">
      <div className={`cond num leading-none font-bold ${size === "lg" ? "text-4xl" : "text-[1.75rem]"} ${color}`}>{value}</div>
      <div className="mt-1 text-[0.85rem] leading-snug text-grafito">{label}</div>
    </div>
  );
}

export function Button({
  children,
  onClick,
  type = "button",
  variant = "secondary",
  disabled,
}: {
  children: ReactNode;
  onClick?: () => void;
  type?: "button" | "submit";
  variant?: "primary" | "secondary";
  disabled?: boolean;
}) {
  const styles =
    variant === "primary"
      ? "bg-boli text-hoja border-boli hover:opacity-90"
      : "bg-hoja text-tinta border-regla hover:border-grafito";
  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      className={`inline-flex h-10 items-center justify-center gap-2 rounded-[3px] border px-4 text-[0.95rem] font-semibold transition-colors disabled:cursor-not-allowed disabled:opacity-50 ${styles}`}
    >
      {children}
    </button>
  );
}

/**
 * Lo que paga la cuota frente a lo que estimamos. La marca vertical es la probabilidad que
 * implica la cuota; el punto, nuestra estimación. El tramo entre ambos es el margen.
 */
export function EdgeBar({ prob, odds, compact = false }: { prob: number; odds: number; compact?: boolean }) {
  const implied = Math.min(1, 1 / odds);
  const lo = Math.min(prob, implied);
  const hi = Math.max(prob, implied);
  const good = prob > implied;
  const text = `La cuota implica ${pct(implied)}; estimamos ${pct(prob)}`;
  return (
    <div className={compact ? "w-full min-w-24" : "w-full"}>
      <div className="relative h-5" title={compact ? text : undefined}>
        <div className="absolute inset-x-0 top-1/2 h-[3px] -translate-y-1/2 rounded-full bg-regla-suave" />
        {[0.25, 0.5, 0.75].map((q) => (
          <div key={q} className="absolute top-1/2 h-2 w-px -translate-y-1/2 bg-regla" style={{ left: `${q * 100}%` }} />
        ))}
        <div
          className={`absolute top-1/2 h-[5px] -translate-y-1/2 rounded-full ${good ? "bg-boli" : "bg-rojo"}`}
          style={{ left: `${lo * 100}%`, width: `${Math.max(0.5, (hi - lo) * 100)}%` }}
        />
        <div className="absolute top-0 h-5 w-[2px] -translate-x-1/2 bg-tinta" style={{ left: `${implied * 100}%` }} />
        <div
          className={`absolute top-1/2 size-3 -translate-x-1/2 -translate-y-1/2 rounded-full border-2 border-hoja ${good ? "bg-boli" : "bg-rojo"}`}
          style={{ left: `${prob * 100}%` }}
        />
      </div>
      {compact ? (
        <span className="sr-only">{text}</span>
      ) : (
        <div className="mt-1.5 flex justify-between gap-4 text-[0.85rem] text-grafito">
          <span>
            La cuota implica <strong className="num font-semibold text-tinta">{pct(implied)}</strong>
          </span>
          <span>
            Estimamos <strong className={`num font-semibold ${good ? "text-boli" : "text-rojo"}`}>{pct(prob)}</strong>
          </span>
        </div>
      )}
    </div>
  );
}

/** Reparto 1X2 en una sola barra: local, empate, visitante */
export function TriBar({
  probs,
  home,
  away,
  size = "sm",
}: {
  probs: { home: number; draw: number; away: number };
  home: string;
  away: string;
  size?: "sm" | "lg";
}) {
  const parts = [
    { key: "home", label: home, p: probs.home, cls: "bg-tinta" },
    { key: "draw", label: "Empate", p: probs.draw, cls: "bg-regla" },
    { key: "away", label: away, p: probs.away, cls: "bg-grafito" },
  ];
  return (
    <div className="w-full">
      <div
        className={`flex w-full gap-[2px] overflow-hidden rounded-[2px] ${size === "lg" ? "h-3" : "h-1.5"}`}
        role="img"
        aria-label={`${home} ${pct(probs.home)}, empate ${pct(probs.draw)}, ${away} ${pct(probs.away)}`}
      >
        {parts.map((x) => (
          <div key={x.key} className={x.cls} style={{ width: `${x.p * 100}%` }} />
        ))}
      </div>
    </div>
  );
}
