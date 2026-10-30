"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { useState } from "react";
import { Crest } from "@/components/Crest";
import { Empty, ErrorNote, Loading, PageTitle, Tag } from "@/components/ui";
import { useApi } from "@/lib/api";
import { AlertTag } from "@/components/semana/Radar";
import { COMPETITIONS, competitionName, stageText } from "@/lib/format";
import { matchesTeams } from "@/lib/search";
import type { MatchSummary } from "@/lib/types";

const DAY_OPTIONS = [3, 7, 10];

export function PartidosView() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const days = Number(params.get("dias")) || 3;
  const comp = params.get("comp") ?? "";
  // El texto vive en el estado para que escribir sea fluido; se copia a la URL para conservarlo al volver de un partido
  const [query, setQuery] = useState(params.get("q") ?? "");
  const { data, error, mutate } = useApi<MatchSummary[]>(`/matches?days=${days}`);

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(params.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  }

  function search(value: string) {
    setQuery(value);
    setParam("q", value.trim());
  }

  const searching = query.trim() !== "";
  const rows = (data ?? []).filter(
    (m) => (!comp || m.competition === comp) && matchesTeams(m.home, m.away, query),
  );
  // "lun 19/10 14:00" → día "lun 19/10" y hora "14:00"
  const groups = new Map<string, MatchSummary[]>();
  for (const m of rows) {
    const dayKey = m.kickoff_local.split(" ").slice(0, 2).join(" ");
    groups.set(dayKey, [...(groups.get(dayKey) ?? []), m]);
  }

  return (
    <>
      <PageTitle title="Partidos" sub="Próximos partidos de las ocho competiciones. Elige uno para ver el análisis completo." />

      <div className="flex flex-wrap items-center gap-x-8 gap-y-3 pb-6">
        <TeamSearch value={query} onChange={search} />
        <fieldset className="flex flex-wrap items-center gap-1">
          <legend className="sr-only">Competición</legend>
          {[["", "Todas"], ...Object.entries(COMPETITIONS)].map(([code, name]) => (
            <FilterButton key={code} active={comp === code} onClick={() => setParam("comp", code)}>
              {name}
            </FilterButton>
          ))}
        </fieldset>
        <fieldset className="flex flex-wrap items-center gap-1">
          <legend className="sr-only">Días</legend>
          {DAY_OPTIONS.map((d) => (
            <FilterButton key={d} active={days === d} onClick={() => setParam("dias", d === 3 ? "" : String(d))}>
              {d} días
            </FilterButton>
          ))}
        </fieldset>
      </div>

      {error ? (
        <ErrorNote error={error} onRetry={() => mutate()} />
      ) : !data ? (
        <Loading lines={6} />
      ) : rows.length === 0 ? (
        searching ? (
          <Empty>
            Ningún partido {comp ? `de ${competitionName(comp)} ` : ""}con «{query.trim()}» en los próximos {days} días.
            {days < DAY_OPTIONS[DAY_OPTIONS.length - 1] && " Prueba con más días."}
          </Empty>
        ) : (
          <Empty>No hay partidos {comp ? `de ${competitionName(comp)} ` : ""}en los próximos {days} días.</Empty>
        )
      ) : (
        <div className="space-y-8 pb-10">
          {searching && (
            <p className="-mt-2 text-nota text-grafito" aria-live="polite">
              {rows.length === 1 ? "1 partido" : `${rows.length} partidos`} con «{query.trim()}»
            </p>
          )}
          {[...groups.entries()].map(([dayKey, ms]) => (
            <section key={dayKey} aria-label={dayKey}>
              <h2 className="semi border-b border-regla pb-2 text-lg font-bold capitalize">{dayKey}</h2>
              <ul className="divide-y divide-regla-suave">
                {ms.map((m) => (
                  <li key={m.match_id}>
                    <Link
                      href={`/partidos/${m.match_id}`}
                      className="grid grid-cols-[3.5rem_1fr] gap-x-4 gap-y-1 py-3 hover:bg-hoja sm:grid-cols-[4rem_minmax(0,1fr)_14rem_11rem] sm:items-center"
                    >
                      <span className="cond num text-2xl font-bold">{m.kickoff_local.split(" ")[2]}</span>
                      <span className="min-w-0">
                        <span className="semi block truncate text-base font-semibold">
                          <Crest id={m.home_id} size={18} className="mr-1.5 -mt-0.5" />
                          {m.home} <span className="font-normal text-grafito">vs</span>{" "}
                          <Crest id={m.away_id} size={18} className="mr-1.5 -mt-0.5" />
                          {m.away}
                        </span>
                        <span className="block text-nota text-grafito">{competitionName(m.competition)}</span>
                        {!!m.alerts?.length && (
                          <span className="mt-1 flex flex-wrap gap-1">
                            {m.alerts.map((a) => (
                              <AlertTag key={a.team_id} alert={a} />
                            ))}
                          </span>
                        )}
                      </span>
                      <span className="col-start-2 truncate text-nota text-grafito sm:col-start-auto">
                        {m.referee ? `Árbitro: ${m.referee}` : "Árbitro sin designar"}
                      </span>
                      <span className="col-start-2 sm:col-start-auto">
                        <Tag tone={m.lineups === "confirmed" ? "confirmada" : "neutral"} className="sm:w-full sm:justify-center">
                          {stageText(m.lineups)}
                        </Tag>
                      </span>
                    </Link>
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      )}
    </>
  );
}

function TeamSearch({ value, onChange }: { value: string; onChange: (value: string) => void }) {
  return (
    <div role="search" className="relative w-full sm:w-72">
      <label htmlFor="buscar-equipo" className="sr-only">
        Buscar equipo
      </label>
      <svg
        aria-hidden="true"
        viewBox="0 0 24 24"
        fill="none"
        stroke="currentColor"
        strokeWidth="2"
        strokeLinecap="round"
        className="pointer-events-none absolute top-1/2 left-3 size-4 -translate-y-1/2 text-grafito"
      >
        <circle cx="11" cy="11" r="7" />
        <path d="m20 20-3.5-3.5" />
      </svg>
      <input
        id="buscar-equipo"
        type="text"
        inputMode="search"
        autoComplete="off"
        spellCheck={false}
        value={value}
        onChange={(e) => onChange(e.target.value)}
        onKeyDown={(e) => {
          if (e.key === "Escape") onChange("");
        }}
        placeholder="Buscar equipo"
        className="h-9 w-full border border-regla bg-hoja pr-9 pl-9 text-interfaz text-tinta placeholder:text-grafito focus:border-boli"
      />
      {value && (
        <button
          type="button"
          onClick={() => onChange("")}
          aria-label="Borrar búsqueda"
          className="absolute top-1/2 right-1 flex size-7 -translate-y-1/2 items-center justify-center text-grafito hover:text-tinta"
        >
          <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="size-4">
            <path d="M6 6l12 12M18 6 6 18" />
          </svg>
        </button>
      )}
    </div>
  );
}

function FilterButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`h-9 border px-3 text-interfaz font-semibold whitespace-nowrap transition-colors ${
        active ? "border-tinta bg-tinta text-papel" : "border-regla bg-hoja text-grafito hover:text-tinta"
      }`}
    >
      {children}
    </button>
  );
}
