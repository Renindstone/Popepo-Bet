"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type FormEvent, type ReactNode, useState } from "react";
import { Cupon } from "@/components/evaluar/Cupon";
import { CuotasCasa } from "@/components/evaluar/CuotasCasa";
import { PenMark } from "@/components/PenMark";
import { RivalryTag } from "@/components/Rivalry";
import { Button, EdgeBar, ErrorNote, Figure, Loading, PageTitle, Section } from "@/components/ui";
import { type ApiError, post, useApi } from "@/lib/api";
import { competitionName, money, odds, pct, signedPct, splitMatch, stageText } from "@/lib/format";
import { betLabel, bookmakerName, MARKET_OPTIONS, type MarketOption, selectionsFor } from "@/lib/markets";
import { addLeg, updateSlip, useSlip } from "@/lib/slip";
import type { BookOdd, Evaluation, MatchAnalysis, MatchSummary, Performance, RegisteredBet } from "@/lib/types";

/** "ou_cards_home" → mercado base "ou_cards" y ámbito "home" */
function parseMarket(raw: string | null): { base: MarketOption; scope: "" | "home" | "away" } {
  let m = (raw ?? "").replace("shots_on_target", "sot");
  let scope: "" | "home" | "away" = "";
  for (const sc of ["home", "away"] as const) {
    if (m.endsWith(`_${sc}`)) {
      m = m.slice(0, -sc.length - 1);
      scope = sc;
    }
  }
  const base = MARKET_OPTIONS.find((o) => o.value === m) ?? MARKET_OPTIONS[0];
  return { base, scope: base.scope ? scope : "" };
}

const GROUPS = [...new Set(MARKET_OPTIONS.map((o) => o.group))];

function lineLabel(market: string, selection: string, t: { home?: string; away?: string }): string {
  const home = t.home ?? "Local";
  const away = t.away ?? "Visitante";
  if (market === "eh") return selection === "away" ? `Hándicap de ${away}` : `Hándicap de ${home}`;
  if (market.startsWith("ah")) return `Hándicap de ${selection === "away" ? away : home}`;
  return "Línea";
}

const field = "h-11 w-full border border-regla bg-hoja px-3 text-base text-tinta focus:border-boli";
const labelCls = "mb-1 block text-nota font-semibold";

export function EvaluarView() {
  const params = useSearchParams();
  const initial = parseMarket(params.get("mercado"));
  const [matchId, setMatchId] = useState(params.get("partido") ?? "");
  const [market, setMarket] = useState<MarketOption>(initial.base);
  const [scope, setScope] = useState<"" | "home" | "away">(initial.scope);
  const [selection, setSelection] = useState(params.get("seleccion") ?? selectionsFor(initial.base.sel)[0].value);
  // En el hándicap 3 vías la API guarda la línea del local; aquí se escribe la del equipo elegido, como en la casa
  const [line, setLine] = useState(() => {
    const raw = params.get("linea");
    if (raw == null) return initial.base.line != null ? String(initial.base.line) : "";
    return initial.base.value === "eh" && params.get("seleccion") === "away" ? String(-Number(raw)) : raw;
  });
  const [player, setPlayer] = useState(params.get("jugador") ?? "");
  const [price, setPrice] = useState(params.get("cuota") ?? "");
  const [bookmaker, setBookmaker] = useState(params.get("casa") === "bet365" ? "bet365" : "betano");
  const [result, setResult] = useState<{ r: Evaluation; matchId: string; player: string | null } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [added, setAdded] = useState<string | null>(null);
  const slip = useSlip();

  const matches = useApi<MatchSummary[]>("/matches?days=7");
  const selected = matches.data?.find((m) => String(m.match_id) === matchId);
  // También sin props: trae el clásico y los avisos de calendario del partido elegido
  const analysis = useApi<MatchAnalysis>(matchId ? `/matches/${matchId}/analysis` : null);
  const teams = { home: selected?.home, away: selected?.away };

  function chooseMarket(value: string) {
    const opt = MARKET_OPTIONS.find((o) => o.value === value) ?? MARKET_OPTIONS[0];
    setMarket(opt);
    if (!opt.scope) setScope("");
    setSelection(selectionsFor(opt.sel)[0].value);
    setLine(opt.line != null ? String(opt.line) : "");
    setResult(null);
  }

  const marketCode = market.value + (scope ? `_${scope}` : "");
  const needsLine = market.line != null;
  const priceNum = Number(price.replace(",", "."));
  const lineNum = Number(line.replace(",", "."));
  const valid =
    !!matchId && priceNum > 1 && (!needsLine || (line !== "" && Number.isFinite(lineNum))) && (!market.player || player.trim() !== "");

  // Línea como la guarda la API: en el hándicap 3 vías, la del local
  const apiLine = needsLine ? (market.value === "eh" && selection === "away" ? -lineNum : lineNum) : null;

  function addToSlip() {
    if (!valid || !selected) return;
    const who = market.player ? player.trim() : null;
    const label = betLabel(marketCode, selection, apiLine, { home: selected.home, away: selected.away, player: who });
    if (slip.legs.length === 0) updateSlip((s) => ({ ...s, bookmaker }));
    addLeg({
      matchId,
      match: `${selected.home} vs ${selected.away}`,
      home: selected.home,
      away: selected.away,
      kickoff: selected.kickoff_local,
      market: marketCode,
      selection,
      line: apiLine,
      player: who,
      odds: priceNum,
      label,
    });
    setAdded(`${label} a ${odds(priceNum)}`);
    setPrice("");
  }

  async function evaluate(body: { market: string; selection: string; odds: number; line: number | null; bookmaker: string; player: string | null }) {
    setBusy(true);
    setError(null);
    try {
      const r = await post<Evaluation>("/odds/evaluate", { match: matchId, ...body });
      setResult({ r, matchId, player: body.player });
    } catch (err) {
      setResult(null);
      setError(err as ApiError);
    } finally {
      setBusy(false);
    }
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    await evaluate({
      market: marketCode,
      selection,
      odds: priceNum,
      line: apiLine,
      bookmaker,
      player: market.player ? player.trim() : null,
    });
  }

  /** Una cuota guardada de Betano: se copia al formulario y se evalúa */
  function pickBookOdd(o: BookOdd) {
    const parsed = parseMarket(o.market);
    setMarket(parsed.base);
    setScope(parsed.scope);
    setSelection(o.selection);
    setLine(o.line == null ? "" : String(parsed.base.value === "eh" && o.selection === "away" ? -o.line : o.line));
    setPrice(String(o.odds));
    setBookmaker("betano");
    setPlayer("");
    window.scrollTo({ top: 0, behavior: "smooth" });
    void evaluate({ market: o.market, selection: o.selection, odds: o.odds, line: o.line, bookmaker: "betano", player: null });
  }

  // Agrupar partidos por día para el desplegable
  const byDay = new Map<string, MatchSummary[]>();
  for (const m of matches.data ?? []) {
    const k = m.kickoff_local.split(" ").slice(0, 2).join(" ");
    byDay.set(k, [...(byDay.get(k) ?? []), m]);
  }

  return (
    <>
      <PageTitle
        title="Evaluar cuota"
        sub="Escribe la cuota que ves en Betano (o bet365) y comprueba si tiene valor según el modelo."
      />
      <div className="grid gap-x-12 gap-y-10 pb-10 lg:grid-cols-[400px_minmax(0,1fr)]">
        <form onSubmit={submit} className="space-y-5" noValidate>
          <div>
            <label htmlFor="partido" className={labelCls}>
              Partido
            </label>
            {matches.error ? (
              <ErrorNote error={matches.error} onRetry={() => matches.mutate()} />
            ) : (
              <select
                id="partido"
                className={field}
                value={matchId}
                onChange={(e) => {
                  setMatchId(e.target.value);
                  setResult(null);
                }}
                disabled={!matches.data}
              >
                <option value="">{matches.data ? "Elige un partido" : "Cargando partidos…"}</option>
                {[...byDay.entries()].map(([day, ms]) => (
                  <optgroup key={day} label={day}>
                    {ms.map((m) => (
                      <option key={m.match_id} value={m.match_id}>
                        {m.kickoff_local.split(" ")[2]} {m.home} vs {m.away} ({competitionName(m.competition)})
                        {m.rivalry ? ` · ${m.rivalry}` : ""}
                      </option>
                    ))}
                  </optgroup>
                ))}
                {matchId && matches.data && !selected && <option value={matchId}>Partido {matchId}</option>}
              </select>
            )}
            <MatchNotes a={analysis.data} />
          </div>

          <div>
            <label htmlFor="mercado" className={labelCls}>
              Mercado
            </label>
            <select id="mercado" className={field} value={market.value} onChange={(e) => chooseMarket(e.target.value)}>
              {GROUPS.map((g) => (
                <optgroup key={g} label={g}>
                  {MARKET_OPTIONS.filter((o) => o.group === g).map((o) => (
                    <option key={o.value} value={o.value}>
                      {o.label}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>

          {market.scope && (
            <Choice
              legend="De quién"
              name="ambito"
              value={scope}
              onChange={(v) => setScope(v as "" | "home" | "away")}
              options={[
                { value: "", label: "Total del partido" },
                { value: "home", label: teams.home ?? "Local" },
                { value: "away", label: teams.away ?? "Visitante" },
              ]}
            />
          )}

          {market.player && (
            <div>
              <label htmlFor="jugador" className={labelCls}>
                Jugador
              </label>
              <input
                id="jugador"
                className={field}
                list="jugadores"
                value={player}
                onChange={(e) => setPlayer(e.target.value)}
                placeholder="Nombre del jugador"
                autoComplete="off"
              />
              <datalist id="jugadores">
                {analysis.data?.players.map((p) => (
                  <option key={p.player_id} value={p.name} />
                ))}
              </datalist>
            </div>
          )}

          <Choice
            legend="Selección"
            name="seleccion"
            value={selection}
            onChange={setSelection}
            options={selectionsFor(market.sel, teams)}
          />

          <div className="grid grid-cols-2 gap-4">
            {needsLine && (
              <div>
                <label htmlFor="linea" className={labelCls}>
                  {lineLabel(market.value, selection, teams)}
                </label>
                <input
                  id="linea"
                  className={`${field} num`}
                  inputMode="decimal"
                  value={line}
                  onChange={(e) => setLine(e.target.value)}
                />
              </div>
            )}
            <div>
              <label htmlFor="cuota" className={labelCls}>
                Cuota
              </label>
              <input
                id="cuota"
                className={`${field} num`}
                inputMode="decimal"
                placeholder="1.85"
                value={price}
                onChange={(e) => setPrice(e.target.value)}
              />
            </div>
          </div>

          {(market.value === "eh" || market.value === "ah") && (
            <p className="-mt-2 text-nota text-grafito">
              {market.value === "eh"
                ? "Escribe el hándicap tal como sale junto al equipo (Coventry +2). Si con el hándicap queda empate, la apuesta al equipo pierde."
                : "Hándicap asiático: si con una línea entera queda empate, se devuelve el dinero; las de cuarto (±0,25, ±0,75) se reparten en dos mitades."}
            </p>
          )}

          <Choice
            legend="Casa"
            name="casa"
            value={bookmaker}
            onChange={setBookmaker}
            options={[
              { value: "betano", label: "Betano" },
              { value: "bet365", label: "bet365" },
            ]}
          />

          <div className="flex flex-wrap gap-3">
            <Button type="submit" variant="primary" disabled={!valid || busy}>
              {busy ? "Evaluando…" : "Evaluar cuota"}
            </Button>
            <Button onClick={addToSlip} disabled={!valid || !selected}>
              Añadir al cupón
            </Button>
          </div>
          <p className="-mt-2 text-nota text-grafito" aria-live="polite">
            {added
              ? `Añadida: ${added}. Sigue con otra selección de este partido (Bet Builder) o elige otro partido.`
              : "Con «Añadir al cupón» puedes juntar varias selecciones, del mismo partido o de otros, y evaluarlas juntas."}
          </p>
        </form>

        <div className="min-w-0 space-y-8">
          <Cupon />
          {error ? (
            <ErrorNote error={error} />
          ) : busy ? (
            <Loading lines={5} label="Evaluando la cuota" />
          ) : result ? (
            <Resultado r={result.r} matchId={result.matchId} player={result.player} />
          ) : slip.legs.length ? null : (
            <Explicacion />
          )}
        </div>
      </div>
      {selected && (
        <Section
          title={`Cuotas de Betano · ${selected.home} vs ${selected.away}`}
          intro="Las que se descargan cada mañana, ya evaluadas por el modelo: no hace falta captura. Pulsa Evaluar para ver el detalle o añádelas al cupón."
        >
          <CuotasCasa match={selected} onUse={pickBookOdd} />
        </Section>
      )}
    </>
  );
}

function Choice({
  legend,
  name,
  value,
  onChange,
  options,
}: {
  legend: string;
  name: string;
  value: string;
  onChange: (v: string) => void;
  options: { value: string; label: string }[];
}) {
  return (
    <fieldset>
      <legend className={labelCls}>{legend}</legend>
      <div className="flex flex-wrap gap-1.5">
        {options.map((o) => (
          <label
            key={o.value}
            className={`flex h-10 cursor-pointer items-center border px-3 text-interfaz font-semibold has-[:focus-visible]:outline-2 has-[:focus-visible]:outline-boli ${
              value === o.value ? "border-tinta bg-tinta text-papel" : "border-regla bg-hoja text-grafito hover:text-tinta"
            }`}
          >
            <input
              type="radio"
              name={name}
              value={o.value}
              checked={value === o.value}
              onChange={() => onChange(o.value)}
              className="sr-only"
            />
            {o.label}
          </label>
        ))}
      </div>
    </fieldset>
  );
}

function Explicacion() {
  return (
    <div className="max-w-[60ch] border-l border-regla pl-5 text-grafito">
      <h2 className="semi mb-2 text-lg font-bold text-tinta">Cómo se decide</h2>
      <p>
        La cuota implica una probabilidad (1 entre la cuota). Si nuestra estimación es mayor, hay valor. En 1X2, goles y
        hándicap la estimación mezcla el modelo con el mercado afilado (Pinnacle o Betfair), porque el backtest muestra que
        el mercado sabe más que el modelo.
      </p>
      <p className="mt-2">
        En props (tarjetas, córners, remates, jugadores) no hay mercado de referencia: la estimación es solo del modelo y la
        confianza es menor.
      </p>
    </div>
  );
}

const VERDICTS: Record<string, { text: string; tone: string }> = {
  APOSTAR: { text: "Apostar", tone: "text-boli" },
  "valor pequeño o poca confianza": { text: "Valor pequeño o poca confianza", tone: "text-tinta" },
  "NO apostar": { text: "No apostar", tone: "text-rojo" },
};

function Resultado({ r, matchId, player }: { r: Evaluation; matchId: string; player: string | null }) {
  const v = VERDICTS[r.verdict] ?? { text: r.verdict, tone: "" };
  const reasons = r.reasons.filter((x) => !x.startsWith("pick_id="));
  const [home, away] = splitMatch(r.match);
  const label = betLabel(r.market, r.selection, r.line, { home, away, player });
  return (
    <article aria-live="polite" className="border border-regla bg-hoja">
      <div className="px-5 pt-5 sm:px-6">
        <p className="text-interfaz text-grafito">
          <Link href={`/partidos/${matchId}`} className="hover:text-boli hover:underline">
            {r.match}
          </Link>
        </p>
        <p className="mt-1 text-entradilla leading-snug font-semibold">
          {label} a {odds(r.odds)} en {bookmakerName(r.bookmaker)}
        </p>
        <div className="relative mt-4 inline-block px-3 py-1">
          {r.verdict === "APOSTAR" && <PenMark className="-inset-x-2 -inset-y-1 h-[calc(100%+0.5rem)] w-[calc(100%+1rem)]" />}
          <p className={`cond text-cifra-grande leading-none font-extrabold ${v.tone}`}>{v.text}</p>
        </div>
        {r.verdict === "valor pequeño o poca confianza" && (
          <p className="mt-2 max-w-[60ch] border-l border-tarjeta pl-3 text-interfaz">
            Tiene valor positivo, pero no pasa el corte que se exige a una apuesta del día (rango de cuota, probabilidad,
            valor y confianza).
          </p>
        )}
      </div>
      <div className="px-5 pt-5 pb-5 sm:px-6">
        <EdgeBar prob={r.prob} odds={r.odds} />
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-5 border-t border-regla-suave px-5 py-5 sm:grid-cols-3 sm:px-6">
        <Figure value={signedPct(r.ev)} label="valor esperado" tone={r.ev > 0 ? "boli" : "rojo"} />
        <Figure value={odds(r.fair_odds)} label="cuota justa" />
        <Figure value={odds(r.min_odds_for_value)} label="cuota mínima para apostar" />
        <Figure value={pct(r.confidence)} label="confianza" />
        <Figure value={pct(r.stake_pct, 1)} label="stake sugerido de la banca" />
        <Figure value={pct(r.model_prob)} label={r.sharp_prob != null ? `modelo (mercado afilado ${pct(r.sharp_prob)})` : "solo modelo"} />
      </div>
      <div className="border-t border-regla-suave px-5 py-4 text-nota text-grafito sm:px-6">
        {reasons.map((x) => (
          <p key={x}>{x}</p>
        ))}
        <p>{stageText(r.lineup_status)}. Si cambia la alineación, vuelve a evaluarla.</p>
      </div>
      <Registrar r={r} matchId={matchId} player={player} />
    </article>
  );
}

function Registrar({ r, matchId, player }: { r: Evaluation; matchId: string; player: string | null }) {
  const perf = useApi<Performance>("/performance");
  const currency = perf.data?.bankroll.currency ?? "PEN";
  const bankroll = perf.data?.bankroll.bankroll;
  const suggested = bankroll && r.stake_pct > 0 ? Math.round(bankroll * r.stake_pct * 100) / 100 : null;
  const [stake, setStake] = useState("");
  const [notes, setNotes] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState<RegisteredBet | null>(null);
  const [error, setError] = useState<ApiError | null>(null);
  const stakeNum = Number(stake.replace(",", "."));

  async function register() {
    setBusy(true);
    setError(null);
    try {
      const res = await post<RegisteredBet>("/bets", {
        match: matchId,
        market: r.market,
        selection: r.selection,
        odds: r.odds,
        line: r.line,
        bookmaker: r.bookmaker,
        player,
        stake: stakeNum,
        notes: notes.trim() || null,
      });
      setDone(res);
      setConfirming(false);
      perf.mutate();
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(false);
    }
  }

  if (done) {
    return (
      <div className="border-t border-regla px-5 py-5 sm:px-6">
        <p className="font-semibold">
          Apuesta registrada (n.º {done.bet_id}): {money(done.stake, done.bankroll.currency)} a {odds(done.odds)}.
        </p>
        <Banca b={done.bankroll} />
        <Link href="/rendimiento" className="mt-2 inline-flex min-h-10 items-center font-semibold text-boli underline underline-offset-4">
          Ver mis apuestas
        </Link>
      </div>
    );
  }

  return (
    <div className="border-t border-regla px-5 py-5 sm:px-6">
      <h3 className="semi text-lg font-bold">Registrar esta apuesta</h3>
      <p className="mt-0.5 max-w-[60ch] text-nota text-grafito">
        Solo si ya la hiciste en tu casa de apuestas. Se liquida sola al terminar el partido y cuenta para tu ROI y tu CLV.
        {r.verdict !== "APOSTAR" && " El modelo no la recomienda; registrarla sirve igual para seguir tu rendimiento."}
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-[10rem_minmax(0,1fr)]">
        <div>
          <label htmlFor="importe" className={labelCls}>
            Importe ({currency === "PEN" ? "S/" : currency})
          </label>
          <input
            id="importe"
            className={`${field} num`}
            inputMode="decimal"
            value={stake}
            placeholder={suggested ? String(suggested) : "10"}
            onChange={(e) => {
              setStake(e.target.value);
              setConfirming(false);
            }}
          />
        </div>
        <div>
          <label htmlFor="notas" className={labelCls}>
            Notas (opcional)
          </label>
          <input id="notas" className={field} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>
      {suggested != null && (
        <p className="mt-2 text-nota text-grafito">
          Stake sugerido: {money(suggested, currency)} ({pct(r.stake_pct, 1)} de una banca de {money(bankroll, currency)}).
        </p>
      )}
      {error && (
        <div className="mt-3">
          <ErrorNote error={error} />
        </div>
      )}
      <div className="mt-4 flex flex-wrap items-center gap-3">
        {!confirming ? (
          <Button onClick={() => setConfirming(true)} disabled={!(stakeNum > 0)}>
            Registrar apuesta
          </Button>
        ) : (
          <>
            <Button variant="primary" onClick={register} disabled={busy}>
              {busy ? "Registrando…" : `Sí, registrar ${money(stakeNum, currency)}`}
            </Button>
            <Button onClick={() => setConfirming(false)} disabled={busy}>
              Cancelar
            </Button>
          </>
        )}
      </div>
    </div>
  );
}

function Banca({ b, children }: { b: Performance["bankroll"]; children?: ReactNode }) {
  return (
    <div className="mt-3 text-interfaz">
      <p className="text-grafito">
        Hoy {money(b.day_profit, b.currency, true)}, esta semana {money(b.week_profit, b.currency, true)}. Pendientes:{" "}
        {b.pending_bets} ({money(b.pending_stake, b.currency)}).
      </p>
      {b.warnings.map((w) => (
        <p key={w} className="mt-2 border-t-[3px] border-rojo bg-rojo-suave px-3 py-2 font-semibold">
          {w}
        </p>
      ))}
      {children}
    </div>
  );
}

/** Lo que conviene saber del partido elegido antes de evaluar una línea: si es un clásico y los avisos de calendario */
function MatchNotes({ a }: { a?: MatchAnalysis }) {
  if (!a) return null;
  const notes = (["home", "away"] as const).flatMap((side) =>
    a.context[side].notes.map((n) => `${side === "home" ? a.home : a.away}: ${n}`),
  );
  if (!a.rivalry && notes.length === 0) return null;
  return (
    <div className="mt-2 space-y-1 text-nota">
      {a.rivalry && (
        <p>
          <RivalryTag name={a.rivalry.name} />{" "}
          <span className="text-grafito">se esperan más faltas y tarjetas que en un partido normal.</span>
        </p>
      )}
      {notes.map((n) => (
        <p key={n} className="text-grafito">
          {n}
        </p>
      ))}
    </div>
  );
}
