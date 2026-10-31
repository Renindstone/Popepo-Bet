"use client";

import Link from "next/link";
import { useState } from "react";
import { ComboResult } from "@/components/ComboResult";
import { Button, ErrorNote, Loading, Tag } from "@/components/ui";
import { type ApiError, post, useApi } from "@/lib/api";
import { money, odds } from "@/lib/format";
import { tr } from "@/lib/i18n";
import { betLabel } from "@/lib/markets";
import type { CaptureCombo, Performance, RegisteredBet } from "@/lib/types";
import {
  clearSlip,
  parseOdds,
  product,
  removeLeg,
  type Slip,
  type SlipLeg,
  slipBlocks,
  updateSlip,
  useSlip,
} from "@/lib/slip";

const field = "h-10 w-full border border-regla bg-papel px-3 text-interfaz text-tinta focus:border-boli";
const labelCls = "mb-1 block text-nota font-semibold";

function blockOdds(slip: Slip, legs: SlipLeg[]): number {
  if (legs.length === 1) return legs[0].odds;
  return parseOdds(slip.blockOdds[legs[0].matchId]) ?? product(legs.map((l) => l.odds));
}

/** Lo que se manda a la API: un bloque por partido con sus selecciones */
function payload(slip: Slip) {
  const blocks = slipBlocks(slip);
  const auto = product(blocks.map((b) => blockOdds(slip, b.legs)));
  return {
    blocks: blocks.map((b) => ({
      match: b.matchId,
      odds: b.legs.length > 1 ? parseOdds(slip.blockOdds[b.matchId]) : null,
      legs: b.legs.map((l) => ({ market: l.market, selection: l.selection, line: l.line, player: l.player, odds: l.odds })),
    })),
    total_odds: parseOdds(slip.totalOdds) ?? auto,
    auto,
  };
}

/** Cupón: varias selecciones de uno o varios partidos (Bet Builders y combinada), evaluadas y registradas juntas. */
export function Cupon() {
  const slip = useSlip();
  const blocks = slipBlocks(slip);
  const { auto, ...body } = payload(slip);
  const key = JSON.stringify(body) + slip.bookmaker;
  const [evaluation, setEvaluation] = useState<{ key: string; combo: CaptureCombo } | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const [registered, setRegistered] = useState<RegisteredBet | null>(null);

  if (registered && slip.legs.length === 0) {
    return (
      <section aria-labelledby="cupon-titulo" className="border border-boli/50 bg-hoja px-5 py-4">
        <h2 id="cupon-titulo" className="semi text-lg font-bold">
          {tr(`Combinada registrada (n.º ${registered.bet_id})`, `Accumulator saved (no. ${registered.bet_id})`)}
        </h2>
        <p className="mt-1 text-interfaz">
          {tr(
            `${money(registered.stake, registered.bankroll.currency)} a ${odds(registered.odds)}. Se liquida sola cuando terminen sus partidos.`,
            `${money(registered.stake, registered.bankroll.currency)} at ${odds(registered.odds)}. It settles on its own when its matches end.`,
          )}
        </p>
        <div className="mt-3 flex flex-wrap gap-4">
          <Link href="/rendimiento" className="font-semibold text-boli underline underline-offset-4">
            {tr("Ver mis apuestas", "See my bets")}
          </Link>
          <button type="button" onClick={() => setRegistered(null)} className="font-semibold text-grafito hover:text-tinta">
            {tr("Cerrar", "Close")}
          </button>
        </div>
      </section>
    );
  }
  if (slip.legs.length === 0) return null;

  async function evaluate() {
    setBusy(true);
    setError(null);
    try {
      const combo = await post<CaptureCombo>("/combos/evaluate", body);
      setEvaluation({ key, combo });
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(false);
    }
  }

  const fresh = evaluation?.key === key ? evaluation.combo : null;
  const nMatches = blocks.length;

  return (
    <section aria-labelledby="cupon-titulo" className="border border-regla bg-hoja">
      <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1 px-5 pt-4 sm:px-6">
        <h2 id="cupon-titulo" className="semi text-lg font-bold">
          {tr("Tu cupón", "Your slip")}
        </h2>
        <p className="text-nota text-grafito">
          {slip.legs.length} {slip.legs.length === 1 ? tr("selección", "selection") : tr("selecciones", "selections")} · {nMatches}{" "}
          {nMatches === 1 ? tr("partido", "match") : tr("partidos", "matches")}
          <button type="button" onClick={clearSlip} className="ml-4 font-semibold text-grafito underline underline-offset-4 hover:text-rojo">
            {tr("Vaciar", "Clear")}
          </button>
        </p>
      </div>

      <ul className="mt-3 space-y-3 px-5 sm:px-6">
        {blocks.map((b) => {
          const first = b.legs[0];
          const builder = b.legs.length > 1;
          return (
            <li key={b.matchId} className="border border-regla-suave px-3 py-2.5">
              <div className="flex flex-wrap items-baseline justify-between gap-x-3">
                <p className="font-semibold">
                  {first.match}
                  <span className="ml-2 text-nota font-normal text-grafito">{first.kickoff}</span>
                </p>
                {builder && <Tag tone="boli">Bet Builder</Tag>}
              </div>
              <ul className="mt-1.5 space-y-1">
                {b.legs.map((l) => {
                  // Se rehace en el idioma en uso: la etiqueta guardada es la del idioma de cuando se añadió
                  const label = betLabel(l.market, l.selection, l.line, { home: l.home, away: l.away, player: l.player });
                  return (
                  <li key={l.id} className="flex items-center justify-between gap-3 text-interfaz">
                    <span className="min-w-0">{label}</span>
                    <span className="flex shrink-0 items-center gap-2">
                      <span className="num font-semibold">{odds(l.odds)}</span>
                      <button
                        type="button"
                        onClick={() => removeLeg(l.id)}
                        aria-label={tr(`Quitar ${label}`, `Remove ${label}`)}
                        className="flex size-7 items-center justify-center text-grafito hover:bg-papel hover:text-rojo"
                      >
                        <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" className="size-4">
                          <path d="M6 6l12 12M18 6 6 18" />
                        </svg>
                      </button>
                    </span>
                  </li>
                  );
                })}
              </ul>
              {builder && (
                <div className="mt-2 grid grid-cols-[9rem_minmax(0,1fr)] items-end gap-3">
                  <div>
                    <label htmlFor={`bb-${b.matchId}`} className={labelCls}>
                      {tr("Cuota del Bet Builder", "Bet Builder odds")}
                    </label>
                    <input
                      id={`bb-${b.matchId}`}
                      className={`${field} num`}
                      inputMode="decimal"
                      placeholder={odds(product(b.legs.map((l) => l.odds)))}
                      value={slip.blockOdds[b.matchId] ?? ""}
                      onChange={(e) => updateSlip((s) => ({ ...s, blockOdds: { ...s.blockOdds, [b.matchId]: e.target.value } }))}
                    />
                  </div>
                  <p className="pb-2 text-nota text-grafito">
                    {tr(
                      "La casa suele pagar menos que el producto de las cuotas: escribe la que te muestra.",
                      "The bookmaker usually pays less than the product of the odds: type the one it shows you.",
                    )}
                  </p>
                </div>
              )}
            </li>
          );
        })}
      </ul>

      <div className="mt-4 grid gap-4 px-5 sm:grid-cols-[9rem_minmax(0,1fr)] sm:px-6">
        <div>
          <label htmlFor="cuota-total" className={labelCls}>
            {tr("Cuota total", "Total odds")}
          </label>
          <input
            id="cuota-total"
            className={`${field} num`}
            inputMode="decimal"
            placeholder={odds(auto)}
            value={slip.totalOdds}
            onChange={(e) => updateSlip((s) => ({ ...s, totalOdds: e.target.value }))}
          />
        </div>
        <fieldset>
          <legend className={labelCls}>{tr("Casa", "Bookmaker")}</legend>
          <div className="flex gap-1.5">
            {[
              ["betano", "Betano"],
              ["bet365", "bet365"],
            ].map(([value, name]) => (
              <button
                key={value}
                type="button"
                aria-pressed={slip.bookmaker === value}
                onClick={() => updateSlip((s) => ({ ...s, bookmaker: value }))}
                className={`h-10 border px-3 text-interfaz font-semibold ${
                  slip.bookmaker === value ? "border-tinta bg-tinta text-papel" : "border-regla bg-papel text-grafito hover:text-tinta"
                }`}
              >
                {name}
              </button>
            ))}
          </div>
        </fieldset>
      </div>

      <div className="mt-4 px-5 pb-5 sm:px-6">
        <Button variant="primary" onClick={evaluate} disabled={busy}>
          {busy ? tr("Evaluando…", "Checking…") : tr("Evaluar cupón", "Check slip")}
        </Button>
        {error && (
          <div className="mt-3">
            <ErrorNote error={error} />
          </div>
        )}
        {busy && (
          <div className="mt-4">
            <Loading lines={3} label={tr("Evaluando el cupón", "Checking the slip")} />
          </div>
        )}
        {!busy && evaluation && !fresh && (
          <p className="mt-3 text-nota text-grafito">
            {tr("Cambiaste el cupón: vuelve a evaluarlo para ver los números al día.", "You changed the slip: check it again to see up-to-date numbers.")}
          </p>
        )}
        {!busy && fresh && (
          <div className="mt-4">
            <ComboResult combo={fresh} />
          </div>
        )}
      </div>

      {slip.legs.length >= 2 && (
        <RegistrarCupon body={body} bookmaker={slip.bookmaker} total={body.total_odds} onDone={setRegistered} />
      )}
    </section>
  );
}

function RegistrarCupon({
  body,
  bookmaker,
  total,
  onDone,
}: {
  body: Omit<ReturnType<typeof payload>, "auto">;
  bookmaker: string;
  total: number;
  onDone: (b: RegisteredBet) => void;
}) {
  const perf = useApi<Performance>("/performance");
  const currency = perf.data?.bankroll.currency ?? "PEN";
  const [stake, setStake] = useState("");
  const [notes, setNotes] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const stakeNum = Number(stake.replace(",", "."));

  async function register() {
    setBusy(true);
    setError(null);
    try {
      const res = await post<RegisteredBet>("/combos", { ...body, stake: stakeNum, bookmaker, notes: notes.trim() || null });
      clearSlip();
      perf.mutate();
      onDone(res);
    } catch (e) {
      setError(e as ApiError);
      setBusy(false);
    }
  }

  return (
    <div className="border-t border-regla px-5 py-5 sm:px-6">
      <h3 className="semi text-base font-bold">{tr("Registrar el cupón", "Record the slip")}</h3>
      <p className="mt-0.5 max-w-[60ch] text-nota text-grafito">
        {tr(
          `Solo si ya lo apostaste. Cuenta como una sola apuesta a cuota ${odds(total)} y se liquida sola cuando terminen sus partidos: basta una selección perdida para perderlo.`,
          `Only if you already placed it. It counts as a single bet at odds ${odds(total)} and settles on its own when its matches end: one lost selection is enough to lose it.`,
        )}
      </p>
      <div className="mt-3 grid gap-4 sm:grid-cols-[9rem_minmax(0,1fr)]">
        <div>
          <label htmlFor="cupon-importe" className={labelCls}>
            {tr("Importe", "Stake")} ({currency === "PEN" ? "S/" : currency})
          </label>
          <input
            id="cupon-importe"
            className={`${field} num`}
            inputMode="decimal"
            placeholder="10"
            value={stake}
            onChange={(e) => {
              setStake(e.target.value);
              setConfirming(false);
            }}
          />
        </div>
        <div>
          <label htmlFor="cupon-notas" className={labelCls}>
            {tr("Notas (opcional)", "Notes (optional)")}
          </label>
          <input id="cupon-notas" className={field} value={notes} onChange={(e) => setNotes(e.target.value)} />
        </div>
      </div>
      {error && (
        <div className="mt-3">
          <ErrorNote error={error} />
        </div>
      )}
      <div className="mt-4 flex flex-wrap gap-3">
        {!confirming ? (
          <Button onClick={() => setConfirming(true)} disabled={!(stakeNum > 0)}>
            {tr("Registrar cupón", "Record slip")}
          </Button>
        ) : (
          <>
            <Button variant="primary" onClick={register} disabled={busy}>
              {busy
                ? tr("Registrando…", "Saving…")
                : tr(`Sí, registrar ${money(stakeNum, currency)} a ${odds(total)}`, `Yes, record ${money(stakeNum, currency)} at ${odds(total)}`)}
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
