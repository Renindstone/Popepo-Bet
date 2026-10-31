"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { type FormEvent, type ReactNode, useEffect, useRef, useState } from "react";
import { Cupon } from "@/components/evaluar/Cupon";
import { CuotasCasa } from "@/components/evaluar/CuotasCasa";
import { PenMark } from "@/components/PenMark";
import { RivalryTag } from "@/components/Rivalry";
import { Button, EdgeBar, ErrorNote, Figure, Loading, PageTitle, Section } from "@/components/ui";
import { type ApiError, post, useApi } from "@/lib/api";
import { COMPETITIONS, competitionName, money, odds, pct, signedPct, splitMatch, stageText } from "@/lib/format";
import { tr } from "@/lib/i18n";
import { betLabel, bookmakerName, marketOptions, type MarketOption, selectionsFor } from "@/lib/markets";
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
  const options = marketOptions();
  const base = options.find((o) => o.value === m) ?? options[0];
  return { base, scope: base.scope ? scope : "" };
}

function lineLabel(market: string, selection: string, t: { home?: string; away?: string }): string {
  const team = selection === "away" ? (t.away ?? tr("Visitante", "Away")) : (t.home ?? tr("Local", "Home"));
  if (market === "eh" || market.startsWith("ah")) return tr(`Hándicap de ${team}`, `${team} handicap`);
  return tr("Línea", "Line");
}

const field = "h-11 w-full border border-regla bg-hoja px-3 text-base text-tinta focus:border-boli";
const labelCls = "mb-1 block text-nota font-semibold";

/**
 * Next 16 conserva la página al navegar (Activity) y el formulario lee la dirección solo al montarse: con la dirección
 * como clave, al llegar con otra apuesta (desde Hoy) se vuelve a montar con ella en vez de seguir con lo de antes.
 */
export function EvaluarView() {
  const params = useSearchParams();
  return <Evaluar key={params.toString()} />;
}

function Evaluar() {
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
  // Liga para acortar la lista de partidos ("" = todas). Si se llega con un partido en la dirección, la suya
  const [leagueChoice, setLeague] = useState<string | null>(null);
  const linked = matches.data?.find((m) => String(m.match_id) === params.get("partido"));
  const league = leagueChoice ?? linked?.competition ?? "";
  // También sin props: trae el clásico y los avisos de calendario del partido elegido
  const analysis = useApi<MatchAnalysis>(matchId ? `/matches/${matchId}/analysis` : null);
  const teams = { home: selected?.home, away: selected?.away };

  const options = marketOptions();
  const groups = [...new Set(options.map((o) => o.group))];

  function chooseMarket(value: string) {
    const opt = options.find((o) => o.value === value) ?? options[0];
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
    setAdded(tr(`${label} a ${odds(priceNum)}`, `${label} at ${odds(priceNum)}`));
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

  function evaluateForm() {
    return evaluate({
      market: marketCode,
      selection,
      odds: priceNum,
      line: apiLine,
      bookmaker,
      player: market.player ? player.trim() : null,
    });
  }

  async function submit(e: FormEvent) {
    e.preventDefault();
    if (!valid) return;
    await evaluateForm();
  }

  // Desde Hoy (la apuesta del día o una que pasa el corte) llega con la cuota: se evalúa al abrir y se baja hasta el
  // resultado, que es donde se registra
  const fromHoy = useRef(!!params.get("cuota"));
  const scrollToResult = useRef(false);
  useEffect(() => {
    if (!fromHoy.current || !valid) return;
    fromHoy.current = false;
    scrollToResult.current = true;
    void evaluateForm();
  });

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
  const leagues = Object.keys(COMPETITIONS)
    .map((code) => ({ code, n: matches.data?.filter((m) => m.competition === code).length ?? 0 }))
    .filter((l) => l.n > 0);
  const byDay = new Map<string, MatchSummary[]>();
  for (const m of (matches.data ?? []).filter((x) => !league || x.competition === league)) {
    const k = m.kickoff_local.split(" ").slice(0, 2).join(" ");
    byDay.set(k, [...(byDay.get(k) ?? []), m]);
  }

  return (
    <>
      <PageTitle
        title={tr("Evaluar cuota", "Check odds")}
        sub={tr(
          "Escribe la cuota que ves en Betano (o bet365) y comprueba si tiene valor según el modelo.",
          "Type the odds you see on Betano (or bet365) and check whether they have value according to the model.",
        )}
      />
      <div className="grid gap-x-12 gap-y-10 pb-10 lg:grid-cols-[400px_minmax(0,1fr)]">
        <form onSubmit={submit} className="space-y-5" noValidate>
          <div>
            <label htmlFor="liga" className={labelCls}>
              {tr("Liga", "League")}
            </label>
            <select
              id="liga"
              className={field}
              value={league}
              onChange={(e) => {
                setLeague(e.target.value);
                if (selected && e.target.value && selected.competition !== e.target.value) {
                  setMatchId("");
                  setResult(null);
                }
              }}
              disabled={!matches.data}
            >
              <option value="">{`${tr("Todas las ligas", "All leagues")} (${matches.data?.length ?? 0})`}</option>
              {leagues.map((l) => (
                <option key={l.code} value={l.code}>
                  {`${competitionName(l.code)} (${l.n})`}
                </option>
              ))}
            </select>
          </div>

          <div>
            <label htmlFor="partido" className={labelCls}>
              {tr("Partido", "Match")}
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
                <option value="">{matches.data ? tr("Elige un partido", "Pick a match") : tr("Cargando partidos…", "Loading matches…")}</option>
                {[...byDay.entries()].map(([day, ms]) => (
                  <optgroup key={day} label={day}>
                    {ms.map((m) => (
                      <option key={m.match_id} value={m.match_id}>
                        {m.kickoff_local.split(" ")[2]} {m.home} vs {m.away}
                        {league ? "" : ` (${competitionName(m.competition)})`}
                        {m.rivalry ? ` · ${m.rivalry}` : ""}
                      </option>
                    ))}
                  </optgroup>
                ))}
                {matchId && matches.data && !selected && (
                  <option value={matchId}>
                    {tr("Partido", "Match")} {matchId}
                  </option>
                )}
              </select>
            )}
            <MatchNotes a={analysis.data} />
          </div>

          <div>
            <label htmlFor="mercado" className={labelCls}>
              {tr("Mercado", "Market")}
            </label>
            <select id="mercado" className={field} value={market.value} onChange={(e) => chooseMarket(e.target.value)}>
              {groups.map((g) => (
                <optgroup key={g} label={g}>
                  {options.filter((o) => o.group === g).map((o) => (
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
              legend={tr("De quién", "Whose")}
              name="ambito"
              value={scope}
              onChange={(v) => setScope(v as "" | "home" | "away")}
              options={[
                { value: "", label: tr("Total del partido", "Match total") },
                { value: "home", label: teams.home ?? tr("Local", "Home") },
                { value: "away", label: teams.away ?? tr("Visitante", "Away") },
              ]}
            />
          )}

          {market.player && (
            <div>
              <label htmlFor="jugador" className={labelCls}>
                {tr("Jugador", "Player")}
              </label>
              <input
                id="jugador"
                className={field}
                list="jugadores"
                value={player}
                onChange={(e) => setPlayer(e.target.value)}
                placeholder={tr("Nombre del jugador", "Player name")}
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
            legend={tr("Selección", "Selection")}
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
                {tr("Cuota", "Odds")}
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
                ? tr(
                    "Escribe el hándicap tal como sale junto al equipo (Coventry +2). Si con el hándicap queda empate, la apuesta al equipo pierde.",
                    "Type the handicap as shown next to the team (Coventry +2). If it ends level with the handicap, the bet on the team loses.",
                  )
                : tr(
                    "Hándicap asiático: si con una línea entera queda empate, se devuelve el dinero; las de cuarto (±0,25, ±0,75) se reparten en dos mitades.",
                    "Asian Handicap: if it ends level on a whole line, the stake is refunded; quarter lines (±0.25, ±0.75) are split into two halves.",
                  )}
            </p>
          )}

          <Choice
            legend={tr("Casa", "Bookmaker")}
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
              {busy ? tr("Evaluando…", "Checking…") : tr("Evaluar cuota", "Check odds")}
            </Button>
            <Button onClick={addToSlip} disabled={!valid || !selected}>
              {tr("Añadir al cupón", "Add to slip")}
            </Button>
          </div>
          <p className="-mt-2 text-nota text-grafito" aria-live="polite">
            {added
              ? tr(
                  `Añadida: ${added}. Sigue con otra selección de este partido (Bet Builder) o elige otro partido.`,
                  `Added: ${added}. Carry on with another selection from this match (Bet Builder) or pick another match.`,
                )
              : tr(
                  "Con «Añadir al cupón» puedes juntar varias selecciones, del mismo partido o de otros, y evaluarlas juntas.",
                  "With “Add to slip” you can put several selections together, from the same match or others, and check them together.",
                )}
          </p>
        </form>

        <div className="min-w-0 space-y-8">
          <Cupon />
          {error ? (
            <ErrorNote error={error} />
          ) : busy ? (
            <Loading lines={5} label={tr("Evaluando la cuota", "Checking the odds")} />
          ) : result ? (
            <div
              ref={(el) => {
                if (el && scrollToResult.current) {
                  scrollToResult.current = false;
                  el.scrollIntoView({ block: "nearest" });
                }
              }}
            >
              <Resultado r={result.r} matchId={result.matchId} player={result.player} />
            </div>
          ) : slip.legs.length ? null : (
            <Explicacion />
          )}
        </div>
      </div>
      {selected && (
        <Section
          title={tr(`Cuotas de Betano · ${selected.home} vs ${selected.away}`, `Betano odds · ${selected.home} vs ${selected.away}`)}
          intro={tr(
            "Las que se descargan cada mañana, ya evaluadas por el modelo: no hace falta captura. Pulsa Evaluar para ver el detalle o añádelas al cupón.",
            "The ones downloaded every morning, already checked by the model: no screenshot needed. Press Check to see the detail or add them to the slip.",
          )}
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
      <h2 className="semi mb-2 text-lg font-bold text-tinta">{tr("Cómo se decide", "How it is decided")}</h2>
      <p>
        {tr(
          "La cuota implica una probabilidad (1 entre la cuota). Si nuestra estimación es mayor, hay valor. En 1X2, goles y hándicap la estimación mezcla el modelo con el mercado afilado (Pinnacle o Betfair), porque el backtest muestra que el mercado sabe más que el modelo.",
          "The odds imply a probability (1 divided by the odds). If our estimate is higher, there is value. In 1X2, goals and handicap the estimate blends the model with the sharp market (Pinnacle or Betfair), because the backtest shows the market knows more than the model.",
        )}
      </p>
      <p className="mt-2">
        {tr(
          "En props (tarjetas, córners, remates, jugadores) no hay mercado de referencia: la estimación es solo del modelo y la confianza es menor.",
          "In props (cards, corners, shots, players) there is no reference market: the estimate comes from the model alone and confidence is lower.",
        )}
      </p>
    </div>
  );
}

// El veredicto llega de la API en español: es la clave
const verdicts = (): Record<string, { text: string; tone: string }> => ({
  APOSTAR: { text: tr("Apostar", "Bet"), tone: "text-boli" },
  "valor pequeño o poca confianza": { text: tr("Valor pequeño o poca confianza", "Small value or low confidence"), tone: "text-tinta" },
  "NO apostar": { text: tr("No apostar", "Don't bet"), tone: "text-rojo" },
});

function Resultado({ r, matchId, player }: { r: Evaluation; matchId: string; player: string | null }) {
  const v = verdicts()[r.verdict] ?? { text: r.verdict, tone: "" };
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
          {tr(`${label} a ${odds(r.odds)} en ${bookmakerName(r.bookmaker)}`, `${label} at ${odds(r.odds)} on ${bookmakerName(r.bookmaker)}`)}
        </p>
        <div className="relative mt-4 inline-block px-3 py-1">
          {r.verdict === "APOSTAR" && <PenMark className="-inset-x-2 -inset-y-1 h-[calc(100%+0.5rem)] w-[calc(100%+1rem)]" />}
          <p className={`cond text-cifra-grande leading-none font-extrabold ${v.tone}`}>{v.text}</p>
        </div>
        {r.verdict === "valor pequeño o poca confianza" && (
          <p className="mt-2 max-w-[60ch] border-l border-tarjeta pl-3 text-interfaz">
            {tr(
              "Tiene valor positivo, pero no pasa el corte que se exige a una apuesta del día (rango de cuota, probabilidad, valor y confianza).",
              "It has positive value, but it does not pass the cut required of a bet of the day (odds range, probability, value and confidence).",
            )}
          </p>
        )}
      </div>
      <div className="px-5 pt-5 pb-5 sm:px-6">
        <EdgeBar prob={r.prob} odds={r.odds} />
      </div>
      <div className="grid grid-cols-2 gap-x-6 gap-y-5 border-t border-regla-suave px-5 py-5 sm:grid-cols-3 sm:px-6">
        <Figure value={signedPct(r.ev)} label={tr("valor esperado", "expected value")} tone={r.ev > 0 ? "boli" : "rojo"} />
        <Figure value={odds(r.fair_odds)} label={tr("cuota justa", "fair odds")} />
        <Figure value={odds(r.min_odds_for_value)} label={tr("cuota mínima para apostar", "minimum odds to bet")} />
        <Figure value={pct(r.confidence)} label={tr("confianza", "confidence")} />
        <Figure value={pct(r.stake_pct, 1)} label={tr("stake sugerido de la banca", "suggested stake of the bankroll")} />
        <Figure
          value={pct(r.model_prob)}
          label={
            r.sharp_prob != null
              ? tr(`modelo (mercado afilado ${pct(r.sharp_prob)})`, `model (sharp market ${pct(r.sharp_prob)})`)
              : tr("solo modelo", "model only")
          }
        />
      </div>
      <div className="border-t border-regla-suave px-5 py-4 text-nota text-grafito sm:px-6">
        {reasons.map((x) => (
          <p key={x}>{x}</p>
        ))}
        <p>
          {stageText(r.lineup_status)}. {tr("Si cambia la alineación, vuelve a evaluarla.", "If the line-up changes, check it again.")}
        </p>
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
          {tr(
            `Apuesta registrada (n.º ${done.bet_id}): ${money(done.stake, done.bankroll.currency)} a ${odds(done.odds)}.`,
            `Bet saved (no. ${done.bet_id}): ${money(done.stake, done.bankroll.currency)} at ${odds(done.odds)}.`,
          )}
        </p>
        <Banca b={done.bankroll} />
        <Link href="/rendimiento" className="mt-2 inline-flex min-h-10 items-center font-semibold text-boli underline underline-offset-4">
          {tr("Ver mis apuestas", "See my bets")}
        </Link>
      </div>
    );
  }

  return (
    <div className="border-t border-regla px-5 py-5 sm:px-6">
      <h3 className="semi text-lg font-bold">{tr("Registrar esta apuesta", "Record this bet")}</h3>
      <p className="mt-0.5 max-w-[60ch] text-nota text-grafito">
        {tr(
          "Solo si ya la hiciste en tu casa de apuestas. Se liquida sola al terminar el partido y cuenta para tu ROI y tu CLV.",
          "Only if you already placed it with your bookmaker. It settles on its own when the match ends and counts towards your ROI and CLV.",
        )}
        {r.verdict !== "APOSTAR" &&
          tr(
            " El modelo no la recomienda; registrarla sirve igual para seguir tu rendimiento.",
            " The model does not recommend it; recording it still helps you track your performance.",
          )}
      </p>
      <div className="mt-4 grid gap-4 sm:grid-cols-[10rem_minmax(0,1fr)]">
        <div>
          <label htmlFor="importe" className={labelCls}>
            {tr("Importe", "Stake")} ({currency === "PEN" ? "S/" : currency})
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
            {tr("Notas (opcional)", "Notes (optional)")}
          </label>
          <input id="notas" className={field} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>
      {suggested != null && (
        <p className="mt-2 text-nota text-grafito">
          {tr(
            `Stake sugerido: ${money(suggested, currency)} (${pct(r.stake_pct, 1)} de una banca de ${money(bankroll, currency)}).`,
            `Suggested stake: ${money(suggested, currency)} (${pct(r.stake_pct, 1)} of a ${money(bankroll, currency)} bankroll).`,
          )}
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
            {tr("Registrar apuesta", "Record bet")}
          </Button>
        ) : (
          <>
            <Button variant="primary" onClick={register} disabled={busy}>
              {busy
                ? tr("Registrando…", "Saving…")
                : tr(`Sí, registrar ${money(stakeNum, currency)} a ${odds(r.odds)}`, `Yes, record ${money(stakeNum, currency)} at ${odds(r.odds)}`)}
            </Button>
            <Button onClick={() => setConfirming(false)} disabled={busy}>
              {tr("Cancelar", "Cancel")}
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
        {tr(
          `Hoy ${money(b.day_profit, b.currency, true)}, esta semana ${money(b.week_profit, b.currency, true)}. Pendientes: ${b.pending_bets} (${money(b.pending_stake, b.currency)}).`,
          `Today ${money(b.day_profit, b.currency, true)}, this week ${money(b.week_profit, b.currency, true)}. Pending: ${b.pending_bets} (${money(b.pending_stake, b.currency)}).`,
        )}
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
          <span className="text-grafito">
            {tr("se esperan más faltas y tarjetas que en un partido normal.", "more fouls and cards than in a normal match are expected.")}
          </span>
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
