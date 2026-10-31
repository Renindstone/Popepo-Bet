import { AlertTag, reasonText } from "@/components/semana/Radar";
import { signedNum } from "@/lib/format";
import { tr } from "@/lib/i18n";
import type { Alert } from "@/lib/types";

function headline(a: Alert): string {
  if (a.reason.type === "batacazo") return tr(`${a.name} viene de un batacazo`, `${a.name} is coming off a big upset`);
  if (a.reason.type === "pinchazo") return tr(`${a.name} viene de un pinchazo`, `${a.name} is coming off a slip-up`);
  return a.kind === "racha"
    ? tr(`${a.name} viene rindiendo por encima de lo esperado`, `${a.name} has been doing better than expected`)
    : tr(`${a.name} viene rindiendo por debajo de lo esperado`, `${a.name} has been doing worse than expected`);
}

function figuresText(a: Alert): string | null {
  if (!a.figures.length) return null;
  const parts = a.figures.map((f) => {
    const where =
      f.lineup === "confirmado"
        ? tr("en el once confirmado", "in the confirmed XI")
        : f.lineup === "probable"
          ? tr("en el once probable", "in the probable XI")
          : f.lineup === "sin_once"
            ? tr("once aún sin publicar", "XI not out yet")
            : tr("fuera del once", "not in the XI");
    return `${f.name} (${signedNum(f.score, 1)}), ${where}`;
  });
  return tr(`Sus figuras: ${parts.join("; ")}.`, `Key players: ${parts.join("; ")}.`);
}

/** Aviso del radar de un equipo del partido: qué pasó, con cuánto lo daba la casa y si sus figuras juegan */
export function AlertBox({ alert }: { alert: Alert }) {
  const figures = figuresText(alert);
  return (
    <div
      className={`max-w-[72ch] border-t-[3px] px-3 py-2.5 text-interfaz ${
        alert.kind === "baja" ? "border-rojo bg-rojo-suave" : "border-tinta bg-tarjeta-suave"
      }`}
    >
      <h4 className="semi text-base leading-snug font-bold">{headline(alert)}</h4>
      <p className="mt-0.5">{reasonText(alert)}</p>
      {figures && <p className="mt-0.5">{figures}</p>}
      <p className="mt-1 text-nota text-grafito">{alert.caveat}</p>
    </div>
  );
}

/** Etiquetas de los avisos de una fila; al tocarlas se abre o se cierra el aviso entero */
export function AlertTags({ alerts, open, onToggle }: { alerts?: Alert[]; open: boolean; onToggle: () => void }) {
  if (!alerts?.length) return null;
  return (
    <button
      type="button"
      onClick={onToggle}
      aria-expanded={open}
      aria-label={tr(
        `${open ? "Ocultar" : "Ver"} el aviso: ${alerts.map((a) => `${a.name} en ${a.kind}`).join(", ")}`,
        `${open ? "Hide" : "Show"} the alert: ${alerts.map((a) => `${a.name} ${a.kind === "racha" ? "on a run" : "in a slump"}`).join(", ")}`,
      )}
      className="mt-1 flex min-h-6 flex-wrap items-center gap-1 text-left"
    >
      {alerts.map((a) => (
        <AlertTag key={a.team_id} alert={a} />
      ))}
    </button>
  );
}

export function AlertList({ alerts, className = "" }: { alerts?: Alert[]; className?: string }) {
  if (!alerts?.length) return null;
  return (
    <div className={`space-y-3 ${className}`}>
      {alerts.map((a) => (
        <AlertBox key={a.team_id} alert={a} />
      ))}
    </div>
  );
}
