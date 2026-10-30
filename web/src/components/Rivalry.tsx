import { Section, Tag } from "@/components/ui";
import { shortDate } from "@/lib/format";
import type { RivalryInfo } from "@/lib/types";

/** «El Clásico», «Derbi de Merseyside»: en estos partidos se ven más faltas y tarjetas de lo normal */
export function RivalryTag({ name }: { name?: string | null }) {
  if (!name) return null;
  return <Tag tone="tarjeta">{name}</Tag>;
}

const COLS = [
  { key: "fouls", label: "Faltas" },
  { key: "cards", label: "Tarjetas" },
  { key: "shots", label: "Remates" },
  { key: "offsides", label: "Offsides" },
] as const;

const th = "py-2 pr-4 text-left text-nota font-semibold text-grafito";
const td = "py-2.5 pr-4 align-top";

function pair(v: [number | null, number | null]): string {
  return v[0] == null || v[1] == null ? "–" : `${v[0]}-${v[1]}`;
}

function pct(f: number | undefined): string {
  return f ? `${Math.round((f - 1) * 100)} %` : "";
}

/** Historial del clásico: los últimos enfrentamientos con faltas, tarjetas, remates y offsides de cada equipo */
export function RivalrySection({ r }: { r: RivalryInfo }) {
  return (
    <Section
      title={r.name}
      intro={`Clásico. Desde 2024 estos partidos traen un ${pct(r.factor.fouls)} más de faltas y un ${pct(r.factor.cards)} más de tarjetas de lo que espera el modelo, ya con el árbitro; lo esperado de este partido ya lo cuenta. En remates, córners, goles y offsides no se distinguen de un partido normal. Cada cifra es local-visitante de ese partido.`}
    >
      {r.matches.length === 0 ? (
        <p className="text-nota text-grafito">Sin enfrentamientos anteriores en los datos.</p>
      ) : (
        <>
          <ul className="divide-y divide-regla-suave border-y border-regla-suave md:hidden">
            {r.matches.map((m) => (
              <li key={m.match_id} className="py-3">
                <p className="font-semibold">
                  {m.home} <span className="num">{m.score}</span> {m.away}
                </p>
                <p className="text-nota text-grafito">{shortDate(m.date)}</p>
                <p className="mt-1 flex flex-wrap gap-x-4 gap-y-1 text-nota">
                  {COLS.map((c) => (
                    <span key={c.key}>
                      {c.label} <strong className="num">{pair(m[c.key])}</strong>
                    </span>
                  ))}
                </p>
              </li>
            ))}
            <li className="py-3 text-nota">
              <span className="font-semibold">Media del total: </span>
              {COLS.map((c) => `${c.label.toLowerCase()} ${r.averages[c.key] ?? "–"}`).join(", ")}
            </li>
          </ul>
          <div className="hidden overflow-x-auto md:block">
            <table className="w-full min-w-[560px] border-collapse text-interfaz">
              <thead className="border-b border-tinta">
                <tr>
                  <th className={th}>Partido</th>
                  {COLS.map((c) => (
                    <th key={c.key} className={`${th} text-right`}>
                      {c.label}
                    </th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {r.matches.map((m) => (
                  <tr key={m.match_id} className="border-b border-regla-suave">
                    <td className={td}>
                      {m.home} <span className="num font-semibold">{m.score}</span> {m.away}
                      <span className="block text-nota text-grafito">{shortDate(m.date)}</span>
                    </td>
                    {COLS.map((c) => (
                      <td key={c.key} className={`${td} num text-right`}>
                        {pair(m[c.key])}
                      </td>
                    ))}
                  </tr>
                ))}
                <tr>
                  <td className={`${td} font-semibold`}>Media del total</td>
                  {COLS.map((c) => (
                    <td key={c.key} className={`${td} num text-right font-semibold`}>
                      {r.averages[c.key] ?? "–"}
                    </td>
                  ))}
                </tr>
              </tbody>
            </table>
          </div>
        </>
      )}
    </Section>
  );
}
