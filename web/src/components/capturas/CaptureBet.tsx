"use client";

import Link from "next/link";
import { useState } from "react";
import { Button, ErrorNote } from "@/components/ui";
import { type ApiError, post, useApi } from "@/lib/api";
import { money, odds } from "@/lib/format";
import type { Performance, RegisteredBet } from "@/lib/types";

const field = "h-10 w-full border border-regla bg-papel px-3 text-interfaz text-tinta focus:border-boli";

/**
 * Registrar como apuesta una cuota de la captura (`line`) o su combinada entera, sin ir a Evaluar cuota.
 * Si Claude vio el importe en la captura, se propone.
 */
export function CaptureBet({
  captureId,
  line,
  price,
  betId,
  defaultStake,
  title,
  onDone,
}: {
  captureId: number;
  line?: number;
  price: number | null;
  betId?: number | null;
  defaultStake?: number | null;
  title: string;
  onDone: () => void;
}) {
  const perf = useApi<Performance>("/performance");
  const currency = perf.data?.bankroll.currency ?? "PEN";
  const [open, setOpen] = useState(false);
  const [stake, setStake] = useState(defaultStake ? String(defaultStake) : "");
  const [confirming, setConfirming] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const stakeNum = Number(stake.replace(",", "."));
  const inputId = `importe-${captureId}-${line ?? "combo"}`;

  if (betId) {
    return (
      <p className="text-nota">
        <span className="font-semibold text-boli">Registrada</span> (apuesta n.º {betId}).{" "}
        <Link href="/rendimiento" className="font-semibold text-boli underline underline-offset-4">
          Ver mis apuestas
        </Link>
      </p>
    );
  }
  if (!open) {
    return (
      <Button onClick={() => setOpen(true)}>
        {title}
      </Button>
    );
  }

  async function register() {
    setBusy(true);
    setError(null);
    try {
      await post<RegisteredBet>(`/captures/${captureId}/bet`, { stake: stakeNum, line: line ?? null });
      perf.mutate();
      onDone();
    } catch (e) {
      setError(e as ApiError);
      setBusy(false);
    }
  }

  return (
    <div className="max-w-md space-y-3 border border-regla-suave p-3">
      <p className="text-nota text-grafito">
        Solo si ya la apostaste{price ? ` a ${odds(price)}` : ""}. Se liquida sola cuando termine y cuenta para tu ROI.
      </p>
      <div className="flex flex-wrap items-end gap-3">
        <div className="w-36">
          <label htmlFor={inputId} className="mb-1 block text-nota font-semibold">
            Importe ({currency === "PEN" ? "S/" : currency})
          </label>
          <input
            id={inputId}
            className={`${field} num`}
            inputMode="decimal"
            placeholder="10"
            autoFocus
            value={stake}
            onChange={(e) => {
              setStake(e.target.value);
              setConfirming(false);
            }}
          />
        </div>
        {!confirming ? (
          <Button onClick={() => setConfirming(true)} disabled={!(stakeNum > 0)}>
            Registrar
          </Button>
        ) : (
          <Button variant="primary" onClick={register} disabled={busy}>
            {busy ? "Registrando…" : `Sí, registrar ${money(stakeNum, currency)}`}
          </Button>
        )}
        <Button onClick={() => setOpen(false)} disabled={busy}>
          Cancelar
        </Button>
      </div>
      {defaultStake != null && stake === String(defaultStake) && (
        <p className="text-nota text-grafito">Importe leído en la captura; cámbialo si no es el que apostaste.</p>
      )}
      {error && <ErrorNote error={error} />}
    </div>
  );
}
