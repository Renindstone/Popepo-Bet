"use client";

import Link from "next/link";
import { usePathname, useRouter, useSearchParams } from "next/navigation";
import { Empty, ErrorNote, Loading, PageTitle, Tag } from "@/components/ui";
import { useApi } from "@/lib/api";
import { COMPETITIONS, competitionName, stageText } from "@/lib/format";
import type { MatchSummary } from "@/lib/types";

const DAY_OPTIONS = [3, 7, 10];

export function PartidosView() {
  const params = useSearchParams();
  const router = useRouter();
  const pathname = usePathname();
  const days = Number(params.get("dias")) || 3;
  const comp = params.get("comp") ?? "";
  const { data, error, mutate } = useApi<MatchSummary[]>(`/matches?days=${days}`);

  function setParam(key: string, value: string) {
    const next = new URLSearchParams(params.toString());
    if (value) next.set(key, value);
    else next.delete(key);
    router.replace(`${pathname}?${next.toString()}`, { scroll: false });
  }

  const rows = (data ?? []).filter((m) => !comp || m.competition === comp);
  // "lun 19/10 14:00" → día "lun 19/10" y hora "14:00"
  const groups = new Map<string, MatchSummary[]>();
  for (const m of rows) {
    const dayKey = m.kickoff_local.split(" ").slice(0, 2).join(" ");
    groups.set(dayKey, [...(groups.get(dayKey) ?? []), m]);
  }

  return (
    <>
      <PageTitle title="Partidos" sub="Próximos partidos de las cuatro competiciones. Elige uno para ver el análisis completo." />

      <div className="flex flex-wrap items-center gap-x-8 gap-y-3 pb-6">
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
        <Empty>No hay partidos {comp ? `de ${competitionName(comp)} ` : ""}en los próximos {days} días.</Empty>
      ) : (
        <div className="space-y-8 pb-10">
          {[...groups.entries()].map(([dayKey, ms]) => (
            <section key={dayKey} aria-label={dayKey}>
              <h2 className="semi border-b border-regla pb-2 text-lg font-bold capitalize">{dayKey}</h2>
              <ul className="divide-y divide-regla-suave">
                {ms.map((m) => (
                  <li key={m.match_id}>
                    <Link
                      href={`/partidos/${m.match_id}`}
                      className="grid grid-cols-[3.5rem_1fr] gap-x-4 gap-y-1 py-3 hover:bg-hoja sm:grid-cols-[4rem_minmax(0,1fr)_14rem_auto] sm:items-center"
                    >
                      <span className="cond num text-2xl font-bold">{m.kickoff_local.split(" ")[2]}</span>
                      <span className="min-w-0">
                        <span className="semi block truncate text-[1.05rem] font-semibold">
                          {m.home} <span className="font-normal text-grafito">vs</span> {m.away}
                        </span>
                        <span className="block text-[0.85rem] text-grafito">{competitionName(m.competition)}</span>
                      </span>
                      <span className="col-start-2 truncate text-[0.9rem] text-grafito sm:col-start-auto">
                        {m.referee ? `Árbitro: ${m.referee}` : "Árbitro sin designar"}
                      </span>
                      <span className="col-start-2 sm:col-start-auto sm:justify-self-end">
                        <Tag tone={m.lineups === "confirmed" ? "boli" : "neutral"}>{stageText(m.lineups)}</Tag>
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

function FilterButton({ active, onClick, children }: { active: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      aria-pressed={active}
      className={`h-9 rounded-[3px] border px-3 text-[0.9rem] font-semibold whitespace-nowrap transition-colors ${
        active ? "border-tinta bg-tinta text-papel" : "border-regla bg-hoja text-grafito hover:text-tinta"
      }`}
    >
      {children}
    </button>
  );
}
