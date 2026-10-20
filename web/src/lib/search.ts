// Búsqueda de equipos tolerante a tildes y mayúsculas: "atletico" encuentra "Atlético Madrid",
// "bodo" encuentra "Bodø/Glimt" y "psg" encuentra "Paris Saint-Germain" (por sus iniciales).

const TRANSLIT: Record<string, string> = { ø: "o", æ: "ae", œ: "oe", ß: "ss", ł: "l", đ: "d", ı: "i", þ: "th", ð: "d" };

export function normalize(text: string): string {
  return text
    .toLowerCase()
    .normalize("NFD")
    .replace(/[̀-ͯ]/g, "")
    .replace(/[øæœßłđıþð]/g, (c) => TRANSLIT[c])
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
}

function initials(name: string): string {
  return normalize(name)
    .split(" ")
    .map((w) => w[0] ?? "")
    .join("");
}

/** Cada palabra buscada debe aparecer en el nombre de alguno de los dos equipos (o en sus iniciales). */
export function matchesTeams(home: string, away: string, query: string): boolean {
  const words = normalize(query).split(" ").filter(Boolean);
  if (words.length === 0) return true;
  const teams = [home, away].map((name) => ({ text: normalize(name), initials: initials(name) }));
  return words.every((w) => teams.some((t) => t.text.includes(w) || (w.length >= 2 && t.initials.startsWith(w))));
}
