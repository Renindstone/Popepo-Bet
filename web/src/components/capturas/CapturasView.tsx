"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Fragment, useCallback, useEffect, useState } from "react";
import { CaptureBet } from "@/components/capturas/CaptureBet";
import { CaptureDrop } from "@/components/capturas/CaptureDrop";
import { ComboResult as Combo, comboVerdictText } from "@/components/ComboResult";
import { Button, EdgeBar, Empty, ErrorNote, Loading, PageTitle, Tag } from "@/components/ui";
import { type ApiError, blobUrl, del, post, put, useApi } from "@/lib/api";
import { competitionName, odds, pct, signedPct } from "@/lib/format";
import { tr } from "@/lib/i18n";
import { betLabel, bookmakerName } from "@/lib/markets";
import { useMe } from "@/lib/me";
import type { Capture, CaptureLine, MatchSummary } from "@/lib/types";

const field = "h-11 w-full border border-regla bg-hoja px-3 text-base text-tinta focus:border-boli";
const labelCls = "mb-1 block text-nota font-semibold";

const ACTIVE = ["pendiente", "procesando", "evaluada"];

/** La captura sigue en manos de la IA (y la página debe refrescarse sola) */
function isActive(c: Capture): boolean {
  return !!c.auto_engine && ACTIVE.includes(c.status);
}

/** Con la IA apagada para este usuario, Capturas no se usa: se explica dónde encenderla */
export function CapturasGate() {
  const { me } = useMe();
  const params = useSearchParams();
  if (me?.ai_enabled === false) {
    return (
      <>
        <PageTitle title={tr("Capturas", "Screenshots")} />
        <p className="max-w-[72ch] border-t-[3px] border-tarjeta bg-tarjeta-suave px-3 py-2 text-interfaz">
          {tr("La IA está apagada para tu usuario: puedes encenderla al final de", "AI is turned off for your user: you can turn it on at the end of")}{" "}
          <Link href="/datos#ia" className="font-bold underline underline-offset-2">
            {tr("Datos", "Data")}
          </Link>
          .
        </p>
      </>
    );
  }
  // Con ?nueva= (la captura recién subida desde Hoy) se vuelve a montar para abrirla: Next conserva la página al navegar
  return <CapturasView key={params.get("nueva") ?? ""} />;
}

export function CapturasView() {
  const params = useSearchParams();
  const fresh = Number(params.get("nueva")) || null;
  const matches = useApi<MatchSummary[]>("/matches?days=7");
  const list = useApi<Capture[]>("/captures?limit=30", {
    refreshInterval: (data) => (data?.some(isActive) ? 2500 : 0),
  });
  const [matchId, setMatchId] = useState("");
  const [bookmaker, setBookmaker] = useState("betano");
  const [note, setNote] = useState("");
  const [open, setOpen] = useState<number | null>(fresh);
  const shown = open ?? list.data?.[0]?.id ?? null;

  const { mutate } = list;
  const onUploaded = useCallback(
    (c: Capture) => {
      setOpen(c.id);
      void mutate();
    },
    [mutate],
  );

  const byDay = new Map<string, MatchSummary[]>();
  for (const m of matches.data ?? []) {
    const k = m.kickoff_local.split(" ").slice(0, 2).join(" ");
    byDay.set(k, [...(byDay.get(k) ?? []), m]);
  }
  const engine = list.data?.[0]?.auto_engine;

  return (
    <>
      <PageTitle
        title={tr("Capturas", "Screenshots")}
        sub={tr(
          "Sube una captura de cuotas de Betano o bet365. Una IA la lee y el modelo te dice qué cuotas tienen valor.",
          "Upload an odds screenshot from Betano or bet365. An AI reads it and the model tells you which odds have value.",
        )}
      />
      <div className="grid gap-x-12 gap-y-10 pb-10 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-5">
          <CaptureDrop onUploaded={onUploaded} match={matchId || undefined} bookmaker={bookmaker} note={note} />
          <div>
            <label htmlFor="partido" className={labelCls}>
              {tr("Partido", "Match")} <span className="font-normal text-grafito">{tr("(opcional)", "(optional)")}</span>
            </label>
            <select id="partido" className={field} value={matchId} onChange={(e) => setMatchId(e.target.value)}>
              <option value="">{tr("Que lo identifique Claude", "Let Claude identify it")}</option>
              {[...byDay.entries()].map(([d, ms]) => (
                <optgroup key={d} label={d}>
                  {ms.map((m) => (
                    <option key={m.match_id} value={String(m.match_id)}>
                      {m.home} vs {m.away} · {competitionName(m.competition)}
                    </option>
                  ))}
                </optgroup>
              ))}
            </select>
          </div>
          <fieldset>
            <legend className={labelCls}>{tr("Casa", "Bookmaker")}</legend>
            <div className="flex gap-2">
              {["betano", "bet365"].map((b) => (
                <label
                  key={b}
                  className={`flex h-10 flex-1 cursor-pointer items-center justify-center border text-interfaz font-semibold ${
                    bookmaker === b ? "border-boli bg-boli-suave text-boli" : "border-regla bg-hoja"
                  }`}
                >
                  <input type="radio" name="casa" value={b} checked={bookmaker === b} onChange={() => setBookmaker(b)} className="sr-only" />
                  {bookmakerName(b)}
                </label>
              ))}
            </div>
          </fieldset>
          <div>
            <label htmlFor="nota" className={labelCls}>
              {tr("Nota para Claude", "Note for Claude")} <span className="font-normal text-grafito">{tr("(opcional)", "(optional)")}</span>
            </label>
            <input
              id="nota"
              className={field}
              value={note}
              maxLength={300}
              placeholder={tr("p. ej. solo me interesan los córners", "e.g. I only care about corners")}
              onChange={(e) => setNote(e.target.value)}
            />
          </div>
          <Explicacion engine={engine} />
        </div>

        <div className="min-w-0">
          {list.error ? (
            <ErrorNote error={list.error} onRetry={() => list.mutate()} />
          ) : !list.data ? (
            <Loading lines={5} />
          ) : list.data.length === 0 ? (
            <Empty>
              {tr(
                "Todavía no has subido capturas. La primera aparecerá aquí en cuanto la sueltes.",
                "You have not uploaded any screenshots yet. The first one will show up here as soon as you drop it.",
              )}
            </Empty>
          ) : (
            <ul className="space-y-3">
              {list.data.map((c) => (
                <li key={c.id}>
                  <CaptureCard
                    c={c}
                    open={shown === c.id}
                    onToggle={() => setOpen(shown === c.id ? -1 : c.id)}
                    onChanged={() => list.mutate()}
                  />
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </>
  );
}

function Explicacion({ engine }: { engine: Capture["auto_engine"] | undefined }) {
  return (
    <div className="border-l border-regla pl-4 text-nota text-grafito">
      <p>
        {tr(
          <>
            La IA solo <strong className="text-tinta">lee</strong> la imagen. La probabilidad, el valor y el veredicto los calcula
            el mismo modelo que en Evaluar cuota. Revisa que las cuotas leídas coincidan con tu captura: si alguna no, corrígela.
          </>,
          <>
            The AI only <strong className="text-tinta">reads</strong> the image. The probability, value and verdict are calculated
            by the same model as in Check odds. Make sure the odds read match your screenshot: if any does not, correct it.
          </>,
        )}
      </p>
      {engine === "local" && (
        <p className="mt-2">
          {tr(
            "La lee una IA en esta PC (Ollama), gratis y sin que la imagen salga de tu equipo. Tarda unos segundos. Si se equivoca con un Bet Builder complicado, corrige las cuotas o pulsa «Leer con Claude».",
            "An AI on this PC (Ollama) reads it, for free and without the image leaving your computer. It takes a few seconds. If it gets a tricky Bet Builder wrong, correct the odds or press “Read with Claude”.",
          )}
        </p>
      )}
      {engine === "claude_code" && (
        <p className="mt-2">
          {tr(
            "La lee Claude Code en esta PC con tu suscripción. Tarda unos segundos por captura.",
            "Claude Code reads it on this PC with your subscription. It takes a few seconds per screenshot.",
          )}
        </p>
      )}
      {engine === "api" && (
        <p className="mt-2">
          {tr("La lee la API de Claude (cada captura tiene un pequeño coste).", "The Claude API reads it (each screenshot has a small cost).")}
        </p>
      )}
      {engine === null && (
        <p className="mt-2">
          {tr(
            "Tus capturas las procesa tu propio agente: pídele «procesa mis capturas pendientes» (herramientas MCP capturas_pendientes y ver_captura).",
            "Your own agent processes your screenshots: ask it to “procesa mis capturas pendientes” (MCP tools capturas_pendientes and ver_captura).",
          )}
        </p>
      )}
    </div>
  );
}

function engineName(engine: string | null | undefined): string {
  const names: Record<string, string> = {
    local: tr("la IA local", "the local AI"),
    claude_code: "Claude",
    api: "Claude (API)",
    mcp: tr("tu agente", "your agent"),
  };
  return names[engine ?? ""] ?? tr("la IA", "the AI");
}

// --------------------------------------------------------------------------- tarjeta de una captura

const statuses = (): Record<string, { text: string; tone: "neutral" | "boli" | "rojo" | "tarjeta" }> => ({
  pendiente: { text: tr("En cola", "Queued"), tone: "neutral" },
  procesando: { text: tr("Leyendo", "Reading"), tone: "tarjeta" },
  evaluada: { text: tr("Resumiendo", "Summarising"), tone: "tarjeta" },
  lista: { text: tr("Lista", "Ready"), tone: "boli" },
  no_evaluable: { text: tr("No evaluable", "Can't evaluate"), tone: "tarjeta" },
  error: { text: "Error", tone: "rojo" },
});

function summaryText(c: Capture): string {
  if (c.combos) {
    const n = c.combos.blocks.length;
    const ev = c.combos.ev != null ? ` (${signedPct(c.combos.ev)})` : "";
    return `${n > 1 ? tr(`Combinada de ${n}`, `${n}-match accumulator`) : "Bet Builder"} · ${comboVerdictText(c.combos.verdict)}${ev}`;
  }
  const s = c.summary;
  if (!s.lines) return "";
  const parts = [tr(`${s.lines} cuota${s.lines === 1 ? "" : "s"}`, `${s.lines} price${s.lines === 1 ? "" : "s"}`)];
  if (s.bet) parts.push(tr(`${s.bet} para apostar`, `${s.bet} to bet`));
  else if (s.positive_ev) parts.push(tr(`${s.positive_ev} con valor pequeño`, `${s.positive_ev} with small value`));
  else parts.push(tr("ninguna con valor", "none with value"));
  if (s.errors) parts.push(tr(`${s.errors} sin evaluar`, `${s.errors} not evaluated`));
  return parts.join(" · ");
}

function useImage(id: number): string | null {
  const [url, setUrl] = useState<string | null>(null);
  useEffect(() => {
    let alive = true;
    let made: string | null = null;
    blobUrl(`/captures/${id}/image`)
      .then((u) => {
        made = u;
        if (alive) setUrl(u);
        else URL.revokeObjectURL(u);
      })
      .catch(() => {});
    return () => {
      alive = false;
      if (made) URL.revokeObjectURL(made);
    };
  }, [id]);
  return url;
}

function CaptureCard({
  c,
  open,
  onToggle,
  onChanged,
}: {
  c: Capture;
  open: boolean;
  onToggle: () => void;
  onChanged: () => void;
}) {
  const img = useImage(c.id);
  const st = c.status === "pendiente" && !c.auto_engine ? { text: tr("Pendiente", "Pending"), tone: "neutral" as const } : statuses()[c.status];
  const blocks = c.combos?.blocks ?? [];
  const title = c.match
    ? `${c.match.home} vs ${c.match.away}`
    : blocks.length > 1
      ? tr(`Combinada: ${blocks.map((b) => b.match).join(" · ")}`, `Accumulator: ${blocks.map((b) => b.match).join(" · ")}`)
      : (blocks[0]?.match ?? c.match_hint ?? tr("Partido por identificar", "Match to be identified"));
  const meta = [
    c.match && `${competitionName(c.match.competition)} · ${c.match.kickoff_local}`,
    c.bookmaker_hint && bookmakerName(c.bookmaker_hint),
    c.created_local && tr(`subida ${c.created_local.slice(11)}`, `uploaded ${c.created_local.slice(11)}`),
  ].filter(Boolean);

  return (
    <article className="border border-regla bg-hoja">
      <button type="button" onClick={onToggle} aria-expanded={open} className="flex w-full items-center gap-4 px-4 py-3 text-left">
        <div className="size-14 shrink-0 overflow-hidden border border-regla bg-papel">
          {/* eslint-disable-next-line @next/next/no-img-element -- imagen local protegida por clave (blob) */}
          {img && <img src={img} alt="" className="size-full object-cover object-top" />}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">{title}</p>
          <p className="truncate text-nota text-grafito">{meta.join(" · ")}</p>
          {(c.status === "lista" || c.status === "no_evaluable") && (
            <p className="truncate text-nota">
              {c.status === "no_evaluable" ? tr("Leída, pero el modelo no puede evaluarla", "Read, but the model can't evaluate it") : summaryText(c)}
            </p>
          )}
        </div>
        <Tag tone={st.tone}>{st.text}</Tag>
      </button>
      {open && <CaptureBody c={c} img={img} onChanged={onChanged} />}
    </article>
  );
}

function CaptureBody({ c, img, onChanged }: { c: Capture; img: string | null; onChanged: () => void }) {
  const [editing, setEditing] = useState(false);
  const [confirmDelete, setConfirmDelete] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<ApiError | null>(null);
  const active = isActive(c);

  async function run(fn: () => Promise<unknown>) {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onChanged();
    } catch (e) {
      setError(e as ApiError);
    } finally {
      setBusy(false);
    }
  }

  return (
    <div className="grid gap-6 border-t border-regla-suave px-4 py-5 lg:grid-cols-[170px_minmax(0,1fr)]">
      <div>
        {img ? (
          <a href={img} target="_blank" rel="noreferrer" title={tr("Ver la captura completa", "See the full screenshot")}>
            {/* eslint-disable-next-line @next/next/no-img-element -- imagen local protegida por clave (blob) */}
            <img
              src={img}
              alt={tr("Captura de cuotas subida", "Uploaded odds screenshot")}
              className="max-h-[420px] w-full border border-regla object-contain object-top"
            />
          </a>
        ) : (
          <div className="esqueleto h-48" />
        )}
      </div>
      <div className="min-w-0 space-y-4">
        {active && (
          <div className="border border-regla-suave p-4">
            <Loading
              lines={3}
              label={
                c.status === "pendiente"
                  ? tr("En cola", "Queued")
                  : c.status === "procesando"
                    ? tr("Leyendo la captura", "Reading the screenshot")
                    : tr("Resumiendo", "Summarising")
              }
            />
            <p className="mt-2 text-nota text-grafito">
              {c.status === "pendiente"
                ? tr("En cola: se procesa en cuanto termine la anterior.", "Queued: it is processed as soon as the previous one finishes.")
                : c.status === "procesando"
                  ? tr(
                      `${engineName(c.engine)[0].toUpperCase()}${engineName(c.engine).slice(1)} está leyendo la captura…`,
                      `${engineName(c.engine)[0].toUpperCase()}${engineName(c.engine).slice(1)} is reading the screenshot…`,
                    )
                  : tr("El modelo ya evaluó las cuotas; falta el resumen…", "The model has evaluated the odds; the summary is on its way…")}
            </p>
          </div>
        )}
        {c.status === "pendiente" && !c.auto_engine && (
          <Empty>
            {tr(
              "Esta captura la procesa tu propio agente. Pídele «procesa mis capturas pendientes» (herramientas MCP capturas_pendientes, ver_captura y evaluar_captura).",
              "Your own agent processes this screenshot. Ask it to “procesa mis capturas pendientes” (MCP tools capturas_pendientes, ver_captura and evaluar_captura).",
            )}
          </Empty>
        )}
        {c.status === "error" && (
          <div role="alert" className="border-t-[3px] border-rojo bg-rojo-suave/60 px-4 py-3">
            <p className="font-semibold">{tr("No se pudo leer la captura", "Could not read the screenshot")}</p>
            <p className="mt-0.5 text-interfaz">{c.error}</p>
          </div>
        )}
        {c.status === "no_evaluable" && (
          <div className="border-t-[3px] border-tarjeta bg-tarjeta-suave px-4 py-3">
            <p className="font-semibold">{tr("Claude leyó la captura, pero el modelo no puede evaluarla", "Claude read the screenshot, but the model can't evaluate it")}</p>
            {c.verdict && <p className="mt-1 max-w-[75ch] text-interfaz whitespace-pre-line">{c.verdict}</p>}
          </div>
        )}
        {c.verdict && c.status !== "no_evaluable" && (
          <div>
            <h3 className="semi text-interfaz font-bold">
              {tr("Resumen", "Summary")}{" "}
              <span className="font-normal text-grafito">· {tr(`leída por ${engineName(c.engine)}`, `read by ${engineName(c.engine)}`)}</span>
            </h3>
            <p className="mt-1 max-w-[75ch] whitespace-pre-line">{c.verdict}</p>
            {c.edited && (
              <p className="mt-2 border-l border-tarjeta pl-3 text-nota">
                {tr(
                  "Corregiste cuotas a mano: este resumen es anterior a la corrección. Los números de la tabla sí están al día.",
                  "You corrected odds by hand: this summary predates the correction. The numbers in the table are up to date.",
                )}
              </p>
            )}
          </div>
        )}
        {c.ai_notes && (
          <p className="text-nota text-grafito">
            <span className="font-semibold text-tinta">{tr("Notas de lectura:", "Reading notes:")}</span> {c.ai_notes}
          </p>
        )}
        {c.combos && <Combo combo={c.combos} />}
        {c.combos && !active && <ComboBet c={c} onDone={onChanged} />}
        {c.lines.length > 0 &&
          (editing ? (
            <EditLines
              c={c}
              onCancel={() => setEditing(false)}
              onSave={(lines) =>
                run(async () => {
                  await put(`/captures/${c.id}/lines`, { match: c.match ? String(c.match.match_id) : null, lines });
                  setEditing(false);
                })
              }
              busy={busy}
            />
          ) : (
            <Lines c={c} onChanged={onChanged} />
          ))}
        {error && <ErrorNote error={error} />}
        {!editing && !active && (
          <div className="flex flex-wrap items-center gap-2 pt-1">
            {c.lines.length > 0 && <Button onClick={() => setEditing(true)}>{tr("Corregir cuotas", "Correct odds")}</Button>}
            {c.auto_engine && (
              <Button onClick={() => run(() => post(`/captures/${c.id}/process`, {}))} disabled={busy}>
                {c.status === "error" ? tr("Reintentar", "Retry") : tr("Volver a leer", "Read again")}
              </Button>
            )}
            {c.fallback_engine && (
              <Button onClick={() => run(() => post(`/captures/${c.id}/process?fallback=true`, {}))} disabled={busy}>
                {tr("Leer con Claude", "Read with Claude")}
              </Button>
            )}
            {!confirmDelete ? (
              <Button onClick={() => setConfirmDelete(true)}>{tr("Borrar", "Delete")}</Button>
            ) : (
              <>
                <Button variant="primary" onClick={() => run(() => del(`/captures/${c.id}`))} disabled={busy}>
                  {tr("Sí, borrar la captura", "Yes, delete the screenshot")}
                </Button>
                <Button onClick={() => setConfirmDelete(false)}>{tr("Cancelar", "Cancel")}</Button>
              </>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

// --------------------------------------------------------------------------- combinadas y Bet Builders

/** Registrar la combinada entera, si todas sus selecciones se pueden liquidar solas */
function ComboBet({ c, onDone }: { c: Capture; onDone: () => void }) {
  const combo = c.combos!;
  const apart = combo.blocks.flatMap((b) =>
    b.match_id == null ? [b.match] : b.legs.filter((lg) => lg.market === "otro").map((lg) => lg.label),
  );
  if (combo.bet_id) {
    return <CaptureBet captureId={c.id} price={combo.total_odds} betId={combo.bet_id} title="" onDone={onDone} />;
  }
  if (apart.length > 0) {
    return (
      <p className="max-w-[75ch] text-nota text-grafito">
        {tr(
          `Para registrarla aquí, todas las selecciones tienen que poder liquidarse solas, y estas no: ${apart.join(", ")}. Si quieres seguirla igual, ármala sin ellas en`,
          `To record it here, every selection has to be able to settle on its own, and these cannot: ${apart.join(", ")}. If you still want to track it, build it without them in`,
        )}{" "}
        <Link href="/evaluar" className="font-semibold text-boli underline underline-offset-4">
          {tr("Evaluar cuota", "Check odds")}
        </Link>
        .
      </p>
    );
  }
  if (!combo.total_odds) return null;
  return (
    <CaptureBet
      captureId={c.id}
      price={combo.total_odds}
      defaultStake={c.stake_seen}
      title={tr(`Registrar esta combinada (cuota ${odds(combo.total_odds)})`, `Record this accumulator (odds ${odds(combo.total_odds)})`)}
      onDone={onDone}
    />
  );
}

// --------------------------------------------------------------------------- cuotas leídas

// El veredicto llega de la API en español: es la clave
const verdicts = (): Record<string, { text: string; tone: "boli" | "tarjeta" | "rojo" }> => ({
  APOSTAR: { text: tr("Apostar", "Bet"), tone: "boli" },
  "valor pequeño o poca confianza": { text: tr("Valor pequeño", "Small value"), tone: "tarjeta" },
  "NO apostar": { text: tr("No apostar", "Don't bet"), tone: "rojo" },
});

function lineLabel(c: Capture, ln: CaptureLine): string {
  return ln.label ?? betLabel(ln.market, ln.selection, ln.line, { home: c.match?.home, away: c.match?.away, player: ln.player });
}

function Lines({ c, onChanged }: { c: Capture; onChanged: () => void }) {
  const [registering, setRegistering] = useState<number | null>(null);
  // Primero las de más valor; las que no se pudieron evaluar, al final. Se recuerda su posición en la captura.
  const rows = c.lines.map((ln, idx) => ({ ...ln, idx })).sort((a, b) => (b.eval?.ev ?? -9) - (a.eval?.ev ?? -9));
  const VERDICTS = verdicts();
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full min-w-[500px] text-interfaz">
        <caption className="sr-only">{tr("Cuotas leídas y su evaluación", "Odds read and their evaluation")}</caption>
        <thead>
          <tr className="border-b border-regla text-left text-nota text-grafito">
            <th className="py-2 pr-3 font-semibold">{tr("Apuesta", "Bet")}</th>
            <th className="py-2 pr-3 text-right font-semibold">{tr("Cuota", "Odds")}</th>
            <th className="py-2 pr-3 font-semibold">{tr("Estimamos", "We estimate")}</th>
            <th className="py-2 pr-3 text-right font-semibold">{tr("Justa", "Fair")}</th>
            <th className="py-2 pr-3 text-right font-semibold">{tr("Valor", "Value")}</th>
            <th className="py-2 pr-3 font-semibold">{tr("Veredicto", "Verdict")}</th>
            <th className="py-2 font-semibold">
              <span className="sr-only">{tr("Acción", "Action")}</span>
            </th>
          </tr>
        </thead>
        <tbody>
          {rows.map((ln, i) => {
            const e = ln.eval;
            const v = e ? VERDICTS[e.verdict] : null;
            return (
              <Fragment key={i}>
              <tr className="border-b border-regla-suave align-middle">
                <td className="py-2 pr-3">
                  <span className="font-medium">{lineLabel(c, ln)}</span>
                  {ln.text && <span className="block text-nota text-grafito">«{ln.text}»</span>}
                </td>
                <td className="num py-2 pr-3 text-right font-semibold">{odds(ln.odds)}</td>
                {e ? (
                  <>
                    <td className="py-2 pr-3">
                      <span className="num">{pct(e.prob)}</span>
                      <EdgeBar prob={e.prob} odds={ln.odds} compact />
                    </td>
                    <td className="num py-2 pr-3 text-right">{odds(e.fair_odds)}</td>
                    <td className={`num py-2 pr-3 text-right font-semibold ${e.ev > 0 ? "text-boli" : "text-rojo"}`}>
                      {signedPct(e.ev)}
                    </td>
                    <td className="py-2 pr-3">{v ? <Tag tone={v.tone}>{v.text}</Tag> : e.verdict}</td>
                    <td className="py-2 text-right">
                      {c.match &&
                        (ln.bet_id ? (
                          <span className="text-nota font-semibold whitespace-nowrap text-boli">{tr("Registrada", "Recorded")}</span>
                        ) : (
                          <button
                            type="button"
                            aria-expanded={registering === ln.idx}
                            onClick={() => setRegistering(registering === ln.idx ? null : ln.idx)}
                            className="text-nota font-semibold whitespace-nowrap text-boli underline underline-offset-4"
                          >
                            {tr("Registrar", "Record")}
                          </button>
                        ))}
                    </td>
                  </>
                ) : (
                  <td colSpan={5} className="py-2 text-nota text-grafito">
                    {ln.error}
                  </td>
                )}
              </tr>
              {registering === ln.idx && (
                <tr className="border-b border-regla-suave">
                  <td colSpan={7} className="py-3">
                    <p className="mb-2 text-nota font-semibold">{tr(`${lineLabel(c, ln)} a ${odds(ln.odds)}`, `${lineLabel(c, ln)} at ${odds(ln.odds)}`)}</p>
                    <CaptureBet
                      captureId={c.id}
                      line={ln.idx}
                      price={ln.odds}
                      defaultStake={c.stake_seen}
                      title={tr("Registrar", "Record")}
                      onDone={() => {
                        setRegistering(null);
                        onChanged();
                      }}
                    />
                  </td>
                </tr>
              )}
              </Fragment>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

interface EditRow {
  ln: CaptureLine;
  odds: string;
  line: string;
  keep: boolean;
}

function EditLines({
  c,
  onSave,
  onCancel,
  busy,
}: {
  c: Capture;
  onSave: (lines: unknown[]) => void;
  onCancel: () => void;
  busy: boolean;
}) {
  const [rows, setRows] = useState<EditRow[]>(() =>
    c.lines.map((ln) => ({ ln, odds: String(ln.odds), line: ln.line == null ? "" : String(ln.line), keep: true })),
  );
  const parsed = rows.map((r) => ({ ...r, o: Number(r.odds.replace(",", ".")), l: r.line === "" ? null : Number(r.line.replace(",", ".")) }));
  const valid = parsed.some((r) => r.keep) && parsed.every((r) => !r.keep || (r.o > 1 && (r.l === null || Number.isFinite(r.l))));

  function set(i: number, patch: Partial<EditRow>) {
    setRows((rs) => rs.map((r, j) => (j === i ? { ...r, ...patch } : r)));
  }

  return (
    <div>
      <p className="mb-3 text-nota text-grafito">
        {tr(
          "Corrige lo que Claude leyó mal. Al guardar, el modelo vuelve a evaluar las cuotas (sin pasar por Claude).",
          "Correct what Claude misread. When you save, the model evaluates the odds again (without going through Claude).",
        )}
      </p>
      <ul className="space-y-2">
        {parsed.map((r, i) => (
          <li key={i} className={`flex flex-wrap items-end gap-3 border border-regla-suave px-3 py-2 ${r.keep ? "" : "opacity-50"}`}>
            <span className="min-w-48 flex-1 font-medium">{lineLabel(c, r.ln)}</span>
            {r.ln.line != null && (
              <label className="text-nota text-grafito">
                {tr("Línea", "Line")}
                <input
                  className={`${field} num mt-0.5 h-9 w-20`}
                  inputMode="decimal"
                  value={r.line}
                  onChange={(e) => set(i, { line: e.target.value })}
                  disabled={!r.keep}
                />
              </label>
            )}
            <label className="text-nota text-grafito">
              {tr("Cuota", "Odds")}
              <input
                className={`${field} num mt-0.5 h-9 w-24`}
                inputMode="decimal"
                value={r.odds}
                onChange={(e) => set(i, { odds: e.target.value })}
                disabled={!r.keep}
              />
            </label>
            <label className="flex h-9 items-center gap-1.5 text-nota">
              <input type="checkbox" checked={!r.keep} onChange={(e) => set(i, { keep: !e.target.checked })} />
              {tr("Quitar", "Remove")}
            </label>
          </li>
        ))}
      </ul>
      <div className="mt-3 flex flex-wrap gap-2">
        <Button
          variant="primary"
          disabled={!valid || busy}
          onClick={() =>
            onSave(
              parsed
                .filter((r) => r.keep)
                .map((r) => ({
                  mercado: r.ln.market,
                  seleccion: r.ln.selection,
                  cuota: r.o,
                  linea: r.l,
                  jugador: r.ln.player,
                  casa: r.ln.bookmaker,
                  texto: r.ln.text,
                })),
            )
          }
        >
          {busy ? tr("Reevaluando…", "Re-evaluating…") : tr("Guardar y reevaluar", "Save and re-evaluate")}
        </Button>
        <Button onClick={onCancel} disabled={busy}>
          {tr("Cancelar", "Cancel")}
        </Button>
      </div>
    </div>
  );
}
