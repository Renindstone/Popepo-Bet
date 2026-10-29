import { TZ } from "@/lib/format";
import type { AiNote } from "@/lib/types";

function when(iso: string | null): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat("es-PE", { timeZone: TZ, day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
    .format(new Date(iso))
    .replace(",", " a las");
}

/** Explicación escrita por Claude a partir de noticias: firmada, con sus fuentes y como texto plano */
export function NotaClaude({ note }: { note: AiNote }) {
  if (note.status === "pendiente" || note.status === "trabajando") {
    return (
      <p role="status" className="mt-2 text-nota text-grafito">
        Claude está leyendo las noticias; la explicación aparece aquí en unos minutos.
      </p>
    );
  }
  if (note.status === "error") {
    return <p className="mt-2 text-nota text-grafito">Claude no pudo escribir la explicación: {note.error}</p>;
  }
  return (
    <div className="mt-3 max-w-[72ch] border-t-[3px] border-tinta bg-tarjeta-suave px-3 py-2.5">
      <h4 className="semi text-base font-bold">Explicación de Claude</h4>
      <p className="mt-1 text-interfaz leading-relaxed whitespace-pre-line">{note.text}</p>
      {note.sources.length > 0 && (
        <ul className="mt-2 space-y-0.5 text-nota">
          {note.sources.map((s) => (
            <li key={s.url}>
              <a href={s.url} target="_blank" rel="noopener noreferrer nofollow" className="underline underline-offset-2">
                {s.title}
              </a>
            </li>
          ))}
        </ul>
      )}
      <p className="mt-1.5 text-nota text-grafito">
        Escrita el {when(note.updated_at)}. Es una lectura de las noticias, no una predicción.
      </p>
    </div>
  );
}
