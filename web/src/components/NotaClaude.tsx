import { TZ } from "@/lib/format";
import { locale, tr } from "@/lib/i18n";
import type { AiNote } from "@/lib/types";

function when(iso: string | null): string {
  if (!iso) return "";
  return new Intl.DateTimeFormat(locale(), { timeZone: TZ, day: "2-digit", month: "2-digit", hour: "2-digit", minute: "2-digit" })
    .format(new Date(iso))
    .replace(",", tr(" a las", " at"));
}

/** Explicación escrita por Claude a partir de noticias: firmada, con sus fuentes y como texto plano */
export function NotaClaude({ note }: { note: AiNote }) {
  if (note.status === "pendiente" || note.status === "trabajando") {
    return (
      <p role="status" className="mt-2 text-nota text-grafito">
        {tr(
          "Claude está leyendo las noticias; la explicación aparece aquí en unos minutos.",
          "Claude is reading the news; the explanation will show up here in a few minutes.",
        )}
      </p>
    );
  }
  if (note.status === "error") {
    return (
      <p className="mt-2 text-nota text-grafito">
        {tr("Claude no pudo escribir la explicación:", "Claude could not write the explanation:")} {note.error}
      </p>
    );
  }
  return (
    <div className="mt-3 max-w-[72ch] border-t-[3px] border-tinta bg-tarjeta-suave px-3 py-2.5">
      <h4 className="semi text-base font-bold">{tr("Explicación de Claude", "Claude's explanation")}</h4>
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
        {tr(
          `Escrita el ${when(note.updated_at)}. Es una lectura de las noticias, no una predicción.`,
          `Written on ${when(note.updated_at)}. It is a reading of the news, not a prediction.`,
        )}
      </p>
    </div>
  );
}
