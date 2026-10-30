// Formato de cifras y fechas: español de Perú, hora de Lima

export const TZ = "America/Lima";
const LOCALE = "es-PE";

const pctFmt = (digits: number) =>
  new Intl.NumberFormat(LOCALE, { style: "percent", minimumFractionDigits: digits, maximumFractionDigits: digits });

export function pct(p: number | null | undefined, digits = 0): string {
  if (p == null || Number.isNaN(p)) return "—";
  return pctFmt(digits).format(p);
}

/** Porcentaje con signo: valor esperado, ROI, CLV */
export function signedPct(p: number | null | undefined, digits = 1): string {
  if (p == null || Number.isNaN(p)) return "—";
  return new Intl.NumberFormat(LOCALE, {
    style: "percent",
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
    signDisplay: "exceptZero",
  }).format(p);
}

export function odds(o: number | null | undefined): string {
  if (o == null || !Number.isFinite(o)) return "—";
  return o.toFixed(2);
}

export function num(n: number | null | undefined, digits = 1): string {
  if (n == null || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat(LOCALE, { minimumFractionDigits: digits, maximumFractionDigits: digits }).format(n);
}

export function int(n: number | null | undefined): string {
  if (n == null) return "—";
  return new Intl.NumberFormat(LOCALE, { maximumFractionDigits: 0 }).format(n);
}

export function money(n: number | null | undefined, currency = "PEN", signed = false): string {
  if (n == null || Number.isNaN(n)) return "—";
  return new Intl.NumberFormat(LOCALE, {
    style: "currency",
    currency,
    signDisplay: signed ? "exceptZero" : "auto",
  }).format(n);
}

/** Línea de un mercado: los hándicaps llevan signo (+1.25), las de más/menos no (2.5) */
export function lineText(market: string, line: number | null | undefined): string {
  if (line == null) return "";
  const s = String(line);
  if (market.startsWith("ah") || market.startsWith("eh")) return line > 0 ? `+${s}` : s;
  return s;
}

/** Fecha y hora de un ISO en hora de Lima: "19 oct, 12:06" */
export function dateTimeLima(iso: string | null | undefined): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return new Intl.DateTimeFormat(LOCALE, {
    timeZone: TZ,
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  }).format(d);
}

/** "hace 2 horas", "hace 3 días" */
export function ago(iso: string | null | undefined, now: Date = new Date()): string {
  if (!iso) return "";
  const diff = (new Date(iso).getTime() - now.getTime()) / 1000;
  const rtf = new Intl.RelativeTimeFormat("es", { numeric: "auto" });
  const abs = Math.abs(diff);
  if (abs < 60) return rtf.format(Math.round(diff), "second");
  if (abs < 3600) return rtf.format(Math.round(diff / 60), "minute");
  if (abs < 86400) return rtf.format(Math.round(diff / 3600), "hour");
  return rtf.format(Math.round(diff / 86400), "day");
}

/** Día de hoy en Lima como YYYY-MM-DD */
export function todayLima(now: Date = new Date()): string {
  return new Intl.DateTimeFormat("en-CA", { timeZone: TZ }).format(now);
}

export function shiftDay(day: string, delta: number): string {
  const [y, m, d] = day.split("-").map(Number);
  const dt = new Date(Date.UTC(y, m - 1, d + delta));
  return dt.toISOString().slice(0, 10);
}

/** Lunes de la semana de un día (YYYY-MM-DD) */
export function weekStart(day: string): string {
  const [y, m, d] = day.split("-").map(Number);
  const weekday = (new Date(Date.UTC(y, m - 1, d)).getUTCDay() + 6) % 7; // lunes = 0
  return shiftDay(day, -weekday);
}

/** "del 19 al 25 de octubre" (o "del 27 de octubre al 2 de noviembre") a partir del lunes */
export function weekLabel(monday: string): string {
  return rangeLabel(monday, shiftDay(monday, 6));
}

/** "del 26 de octubre al 22 de noviembre" entre dos fechas AAAA-MM-DD */
export function rangeLabel(start: string, end: string): string {
  const fmt = (day: string, month: boolean) => {
    const [y, m, d] = day.split("-").map(Number);
    return new Intl.DateTimeFormat(LOCALE, { timeZone: "UTC", day: "numeric", ...(month ? { month: "long" } : {}) }).format(
      new Date(Date.UTC(y, m - 1, d)),
    );
  };
  return `del ${fmt(start, start.slice(5, 7) !== end.slice(5, 7))} al ${fmt(end, true)}`;
}

/** Lunes desde el que hay un mes (4 semanas completas) con la previa guardada desde `historySince` */
export function monthAvailableFrom(historySince: string | null | undefined): string | null {
  if (!historySince) return null;
  const monday = weekStart(historySince);
  const firstFull = monday === historySince ? monday : shiftDay(monday, 7);
  return shiftDay(firstFull, 28);
}

/** Número con signo: +0.77, −0.47 (0 sin signo) */
export function signedNum(n: number | null | undefined, digits = 2): string {
  if (n == null || Number.isNaN(n)) return "—";
  const s = Math.abs(n).toFixed(digits);
  return n > 0 ? `+${s}` : n < 0 ? `−${s}` : s;
}

/** "Vinícius Júnior" → "Vinícius Jr."; "Kylian Mbappé" → "Mbappé" (como en FotMob, el apellido) */
export function shortName(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 1) return name;
  const last = parts[parts.length - 1];
  if (/^(júnior|junior|jr\.?)$/i.test(last)) return `${parts[parts.length - 2]} Jr.`;
  return last;
}

/** "lunes 19 de octubre" a partir de YYYY-MM-DD */
export function longDay(day: string): string {
  const [y, m, d] = day.split("-").map(Number);
  return new Intl.DateTimeFormat(LOCALE, { timeZone: "UTC", weekday: "long", day: "numeric", month: "long" }).format(
    new Date(Date.UTC(y, m - 1, d)),
  );
}

/** "19/10/2026" a partir de YYYY-MM-DD */
export function shortDate(day: string | null | undefined): string {
  if (!day) return "—";
  const [y, m, d] = day.slice(0, 10).split("-");
  return `${d}/${m}/${y}`;
}

export const COMPETITIONS: Record<string, string> = {
  EPL: "Premier League",
  BUN: "Bundesliga",
  LAL: "LaLiga",
  SA: "Serie A",
  L1: "Ligue 1",
  POR: "Primeira Liga",
  BEL: "Pro League",
  UCL: "Champions League",
};

export function competitionName(code: string): string {
  return COMPETITIONS[code] ?? code;
}

export const STAGES: Record<string, string> = {
  confirmed: "Alineaciones confirmadas",
  predicted: "Alineaciones previstas",
  injuries_only: "Solo bajas conocidas",
  none: "Sin alineaciones",
};

export function stageText(stage: string | null | undefined): string {
  if (!stage) return "Sin alineaciones";
  return STAGES[stage] ?? stage;
}

export const RESULTS: Record<string, string> = {
  win: "Ganada",
  half_win: "Medio ganada",
  push: "Devuelta",
  half_loss: "Medio perdida",
  loss: "Perdida",
  void: "Anulada",
};

/** Tono de la etiqueta de un resultado: azul si se ganó, rojo si se perdió (siempre con su palabra) */
export const RESULT_TONE: Record<string, "boli" | "rojo" | "neutral"> = {
  win: "boli",
  half_win: "boli",
  loss: "rojo",
  half_loss: "rojo",
};

export function resultText(r: string | null | undefined): string {
  if (!r) return "Pendiente";
  return RESULTS[r] ?? r;
}

/** "Tottenham Hotspur vs Coventry City" → ["Tottenham Hotspur", "Coventry City"] */
export function splitMatch(match: string): [string, string] {
  const i = match.indexOf(" vs ");
  if (i < 0) return [match, ""];
  return [match.slice(0, i), match.slice(i + 4)];
}
