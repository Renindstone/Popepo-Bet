"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import { Fragment, useCallback, useEffect, useState } from "react";
import { CaptureBet } from "@/components/capturas/CaptureBet";
import { CaptureDrop } from "@/components/capturas/CaptureDrop";
import { ComboResult as Combo } from "@/components/ComboResult";
import { Button, EdgeBar, Empty, ErrorNote, Loading, PageTitle, Tag } from "@/components/ui";
import { type ApiError, blobUrl, del, post, put, useApi } from "@/lib/api";
import { competitionName, odds, pct, signedPct } from "@/lib/format";
import { betLabel, bookmakerName } from "@/lib/markets";
import type { Capture, CaptureLine, MatchSummary } from "@/lib/types";

const field = "h-11 w-full rounded-[3px] border border-regla bg-hoja px-3 text-[1rem] text-tinta focus:border-boli";
const labelCls = "mb-1 block text-[0.9rem] font-semibold";

const ACTIVE = ["pendiente", "procesando", "evaluada"];

/** La captura sigue en manos de la IA (y la página debe refrescarse sola) */
function isActive(c: Capture): boolean {
  return !!c.auto_engine && ACTIVE.includes(c.status);
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
        title="Capturas"
        sub="Sube una captura de cuotas de Betano o bet365. Claude la lee y el modelo te dice qué cuotas tienen valor."
      />
      <div className="grid gap-x-12 gap-y-10 pb-10 lg:grid-cols-[320px_minmax(0,1fr)]">
        <div className="space-y-5">
          <CaptureDrop onUploaded={onUploaded} match={matchId || undefined} bookmaker={bookmaker} note={note} />
          <div>
            <label htmlFor="partido" className={labelCls}>
              Partido <span className="font-normal text-grafito">(opcional)</span>
            </label>
            <select id="partido" className={field} value={matchId} onChange={(e) => setMatchId(e.target.value)}>
              <option value="">Que lo identifique Claude</option>
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
            <legend className={labelCls}>Casa</legend>
            <div className="flex gap-2">
              {["betano", "bet365"].map((b) => (
                <label
                  key={b}
                  className={`flex h-10 flex-1 cursor-pointer items-center justify-center rounded-[3px] border text-[0.95rem] font-semibold ${
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
              Nota para Claude <span className="font-normal text-grafito">(opcional)</span>
            </label>
            <input
              id="nota"
              className={field}
              value={note}
              maxLength={300}
              placeholder="p. ej. solo me interesan los córners"
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
            <Empty>Todavía no has subido capturas. La primera aparecerá aquí en cuanto la sueltes.</Empty>
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
    <div className="border-l-2 border-regla pl-4 text-[0.92rem] text-grafito">
      <p>
        Claude solo <strong className="text-tinta">lee</strong> la imagen. La probabilidad, el valor y el veredicto los calcula el
        mismo modelo que en Evaluar cuota. Revisa que las cuotas leídas coincidan con tu captura: si alguna no, corrígela.
      </p>
      {engine === "claude_code" && (
        <p className="mt-2">La lee Claude Code en esta PC con tu suscripción. Tarda unos segundos por captura.</p>
      )}
      {engine === "api" && <p className="mt-2">La lee la API de Claude (cada captura tiene un pequeño coste).</p>}
      {engine === null && (
        <p className="mt-2">
          Tus capturas las procesa tu propio agente: pídele «procesa mis capturas pendientes» (herramientas MCP
          capturas_pendientes y ver_captura).
        </p>
      )}
    </div>
  );
}

// --------------------------------------------------------------------------- tarjeta de una captura

const STATUS: Record<string, { text: string; tone: "neutral" | "boli" | "rojo" | "tarjeta" }> = {
  pendiente: { text: "En cola", tone: "neutral" },
  procesando: { text: "Claude está leyendo", tone: "tarjeta" },
  evaluada: { text: "Resumiendo", tone: "tarjeta" },
  lista: { text: "Lista", tone: "boli" },
  no_evaluable: { text: "No evaluable", tone: "tarjeta" },
  error: { text: "Error", tone: "rojo" },
};

function summaryText(c: Capture): string {
  if (c.combos) {
    const n = c.combos.blocks.length;
    const ev = c.combos.ev != null ? ` (${signedPct(c.combos.ev)})` : "";
    return `${n > 1 ? `Combinada de ${n}` : "Bet Builder"} · ${c.combos.verdict}${ev}`;
  }
  const s = c.summary;
  if (!s.lines) return "";
  const parts = [`${s.lines} cuota${s.lines === 1 ? "" : "s"}`];
  if (s.bet) parts.push(`${s.bet} para apostar`);
  else if (s.positive_ev) parts.push(`${s.positive_ev} con valor pequeño`);
  else parts.push("ninguna con valor");
  if (s.errors) parts.push(`${s.errors} sin evaluar`);
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
  const st = c.status === "pendiente" && !c.auto_engine ? { text: "Pendiente", tone: "neutral" as const } : STATUS[c.status];
  const blocks = c.combos?.blocks ?? [];
  const title = c.match
    ? `${c.match.home} vs ${c.match.away}`
    : blocks.length > 1
      ? `Combinada: ${blocks.map((b) => b.match).join(" · ")}`
      : (blocks[0]?.match ?? c.match_hint ?? "Partido por identificar");
  const meta = [
    c.match && `${competitionName(c.match.competition)} · ${c.match.kickoff_local}`,
    c.bookmaker_hint && bookmakerName(c.bookmaker_hint),
    c.created_local && `subida ${c.created_local.slice(11)}`,
  ].filter(Boolean);

  return (
    <article className="rounded-[4px] border border-regla bg-hoja">
      <button type="button" onClick={onToggle} aria-expanded={open} className="flex w-full items-center gap-4 px-4 py-3 text-left">
        <div className="size-14 shrink-0 overflow-hidden rounded-[3px] border border-regla bg-papel">
          {/* eslint-disable-next-line @next/next/no-img-element -- imagen local protegida por clave (blob) */}
          {img && <img src={img} alt="" className="size-full object-cover object-top" />}
        </div>
        <div className="min-w-0 flex-1">
          <p className="truncate font-semibold">{title}</p>
          <p className="truncate text-[0.88rem] text-grafito">{meta.join(" · ")}</p>
          {(c.status === "lista" || c.status === "no_evaluable") && (
            <p className="truncate text-[0.88rem]">{c.status === "no_evaluable" ? "Leída, pero el modelo no puede evaluarla" : summaryText(c)}</p>
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
          <a href={img} target="_blank" rel="noreferrer" title="Ver la captura completa">
            {/* eslint-disable-next-line @next/next/no-img-element -- imagen local protegida por clave (blob) */}
            <img src={img} alt="Captura de cuotas subida" className="max-h-[420px] w-full rounded-[3px] border border-regla object-contain object-top" />
          </a>
        ) : (
          <div className="esqueleto h-48 rounded-[3px]" />
        )}
      </div>
      <div className="min-w-0 space-y-4">
        {active && (
          <div className="rounded-[3px] border border-regla-suave p-4">
            <Loading
              lines={3}
              label={c.status === "pendiente" ? "En cola" : c.status === "procesando" ? "Claude está leyendo la captura" : "Claude está resumiendo"}
            />
            <p className="mt-2 text-[0.9rem] text-grafito">
              {c.status === "pendiente"
                ? "En cola: se procesa en cuanto termine la anterior."
                : c.status === "procesando"
                  ? "Claude está leyendo la captura…"
                  : "El modelo ya evaluó las cuotas; Claude está escribiendo el resumen…"}
            </p>
          </div>
        )}
        {c.status === "pendiente" && !c.auto_engine && (
          <Empty>
            Esta captura la procesa tu propio agente. Pídele «procesa mis capturas pendientes» (herramientas MCP
            capturas_pendientes, ver_captura y evaluar_captura).
          </Empty>
        )}
        {c.status === "error" && (
          <div role="alert" className="border-l-[3px] border-rojo bg-rojo-suave/60 px-4 py-3">
            <p className="font-semibold">No se pudo leer la captura</p>
            <p className="mt-0.5 text-[0.95rem]">{c.error}</p>
          </div>
        )}
        {c.status === "no_evaluable" && (
          <div className="border-l-[3px] border-tarjeta bg-tarjeta-suave px-4 py-3">
            <p className="font-semibold">Claude leyó la captura, pero el modelo no puede evaluarla</p>
            {c.verdict && <p className="mt-1 max-w-[75ch] text-[0.95rem] whitespace-pre-line">{c.verdict}</p>}
          </div>
        )}
        {c.verdict && c.status !== "no_evaluable" && (
          <div>
            <h3 className="semi text-[0.95rem] font-bold">Resumen de Claude</h3>
            <p className="mt-1 max-w-[75ch] whitespace-pre-line">{c.verdict}</p>
            {c.edited && (
              <p className="mt-2 border-l-[3px] border-tarjeta pl-3 text-[0.9rem]">
                Corregiste cuotas a mano: este resumen es anterior a la corrección. Los números de la tabla sí están al día.
              </p>
            )}
          </div>
        )}
        {c.ai_notes && (
          <p className="text-[0.9rem] text-grafito">
            <span className="font-semibold text-tinta">Notas de lectura:</span> {c.ai_notes}
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
            {c.lines.length > 0 && <Button onClick={() => setEditing(true)}>Corregir cuotas</Button>}
            {c.auto_engine && (
              <Button onClick={() => run(() => post(`/captures/${c.id}/process`, {}))} disabled={busy}>
                {c.status === "error" ? "Reintentar" : "Volver a leer"}
              </Button>
            )}
            {!confirmDelete ? (
              <Button onClick={() => setConfirmDelete(true)}>Borrar</Button>
            ) : (
              <>
                <Button variant="primary" onClick={() => run(() => del(`/captures/${c.id}`))} disabled={busy}>
                  Sí, borrar la captura
                </Button>
                <Button onClick={() => setConfirmDelete(false)}>Cancelar</Button>
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
      <p className="max-w-[75ch] text-[0.88rem] text-grafito">
        Para registrarla aquí, todas las selecciones tienen que poder liquidarse solas, y estas no: {apart.join(", ")}.
        Si quieres seguirla igual, ármala sin ellas en{" "}
        <Link href="/evaluar" className="font-semibold text-boli underline underline-offset-4">
          Evaluar cuota
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
      title={`Registrar esta combinada (cuota ${odds(combo.total_odds)})`}
      onDone={onDone}
    />
  );
}

// --------------------------------------------------------------------------- cuotas leídas

const VERDICTS: Record<string, { text: string; tone: "boli" | "tarjeta" | "rojo" }> = {
  APOSTAR: { text: "Apostar", tone: "boli" },
  "valor pequeño o poca confianza": { text: "Valor pequeño", tone: "tarjeta" },
  "NO apostar": { text: "No apostar", tone: "rojo" },
};

function lineLabel(c: Capture, ln: CaptureLine): string {
  return ln.label ?? betLabel(ln.market, ln.selection, ln.line, { home: c.match?.home, away: c.match?.away, player: ln.player });
}

function Lines({ c, onChanged }: { c: Capture; onChanged: () => void }) {
  const [registering, setRegistering] = useState<number | null>(null);
  // Primero las de más valor; las que no se pudieron evaluar, al final. Se recuerda su posición en la captura.
  const rows = c.lines.map((ln, idx) => ({ ...ln, idx })).sort((a, b) => (b.eval?.ev ?? -9) - (a.eval?.ev ?? -9));
  return (
    <div className="relative overflow-x-auto">
      <table className="w-full min-w-[500px] text-[0.93rem]">
        <caption className="sr-only">Cuotas leídas y su evaluación</caption>
        <thead>
          <tr className="border-b border-regla text-left text-[0.82rem] text-grafito">
            <th className="py-2 pr-3 font-semibold">Apuesta</th>
            <th className="py-2 pr-3 text-right font-semibold">Cuota</th>
            <th className="py-2 pr-3 font-semibold">Estimamos</th>
            <th className="py-2 pr-3 text-right font-semibold">Justa</th>
            <th className="py-2 pr-3 text-right font-semibold">Valor</th>
            <th className="py-2 pr-3 font-semibold">Veredicto</th>
            <th className="py-2 font-semibold">
              <span className="sr-only">Acción</span>
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
                  {ln.text && <span className="block text-[0.82rem] text-grafito">«{ln.text}»</span>}
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
                          <span className="text-[0.85rem] font-semibold whitespace-nowrap text-boli">Registrada</span>
                        ) : (
                          <button
                            type="button"
                            aria-expanded={registering === ln.idx}
                            onClick={() => setRegistering(registering === ln.idx ? null : ln.idx)}
                            className="text-[0.88rem] font-semibold whitespace-nowrap text-boli underline underline-offset-4"
                          >
                            Registrar
                          </button>
                        ))}
                    </td>
                  </>
                ) : (
                  <td colSpan={5} className="py-2 text-[0.88rem] text-grafito">
                    {ln.error}
                  </td>
                )}
              </tr>
              {registering === ln.idx && (
                <tr className="border-b border-regla-suave">
                  <td colSpan={7} className="py-3">
                    <p className="mb-2 text-[0.92rem] font-semibold">{lineLabel(c, ln)} a {odds(ln.odds)}</p>
                    <CaptureBet
                      captureId={c.id}
                      line={ln.idx}
                      price={ln.odds}
                      defaultStake={c.stake_seen}
                      title="Registrar"
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
      <p className="mb-3 text-[0.92rem] text-grafito">
        Corrige lo que Claude leyó mal. Al guardar, el modelo vuelve a evaluar las cuotas (sin pasar por Claude).
      </p>
      <ul className="space-y-2">
        {parsed.map((r, i) => (
          <li key={i} className={`flex flex-wrap items-end gap-3 rounded-[3px] border border-regla-suave px-3 py-2 ${r.keep ? "" : "opacity-50"}`}>
            <span className="min-w-48 flex-1 font-medium">{lineLabel(c, r.ln)}</span>
            {r.ln.line != null && (
              <label className="text-[0.82rem] text-grafito">
                Línea
                <input
                  className={`${field} num mt-0.5 h-9 w-20`}
                  inputMode="decimal"
                  value={r.line}
                  onChange={(e) => set(i, { line: e.target.value })}
                  disabled={!r.keep}
                />
              </label>
            )}
            <label className="text-[0.82rem] text-grafito">
              Cuota
              <input
                className={`${field} num mt-0.5 h-9 w-24`}
                inputMode="decimal"
                value={r.odds}
                onChange={(e) => set(i, { odds: e.target.value })}
                disabled={!r.keep}
              />
            </label>
            <label className="flex h-9 items-center gap-1.5 text-[0.88rem]">
              <input type="checkbox" checked={!r.keep} onChange={(e) => set(i, { keep: !e.target.checked })} />
              Quitar
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
          {busy ? "Reevaluando…" : "Guardar y reevaluar"}
        </Button>
        <Button onClick={onCancel} disabled={busy}>
          Cancelar
        </Button>
      </div>
    </div>
  );
}
