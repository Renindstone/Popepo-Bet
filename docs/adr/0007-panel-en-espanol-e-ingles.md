# ADR 0007: Dashboard in Spanish and English

**English** · [Español](../es/adr/0007-panel-en-espanol-e-ingles.md)

**Status**: accepted (2026-10-31). Rebuilt on 10-11-2026 from what the owner said, commit `6dc31b6`,
`api/i18n.py` and `docs/arquitectura.md`: the original only lived on their PC and was lost.

## Context
The owner wants the project to reach more people on GitHub, including English speakers. The same day the
repository got an MIT license and a README with an English section, but the dashboard was only in Spanish.
They asked to translate **everything** that's visible, including the texts the server builds: reasons, warnings,
notes and errors.

The whole program is written in Spanish (services, database, bot, MCP and the texts they generate), and
rewriting it in two languages would touch almost every module.

## Decision
- **ES / EN selector** in the dashboard header. The browser remembers it and, if nothing was chosen, it follows
  the browser's language (if it's neither Spanish nor English, Spanish).
- **Dashboard texts**: every text carries both versions where it's used (`tr("Hoy", "Today")`,
  `web/src/lib/i18n.tsx`), with no separate translation files. Switching language remounts the dashboard.
- **API texts**: the dashboard sends `Accept-Language` with every request and, if it's English, a middleware
  (`api/i18n.py`) translates the JSON response with a catalogue of fixed phrases and templates. Whatever isn't in
  the catalogue goes out as it is.
- **What doesn't change**: the services, the database, the Telegram bot and the MCP stay in Spanish. The values the
  dashboard uses as keys ("APOSTAR", "con valor", "racha", the difficulty levels…) aren't translated in the API but
  in the dashboard, so the comparisons don't break.
- Markets with Betano's English names ("Asian Handicap", "Both Teams To Score"), dates in British English and money
  always in soles.

## Consequences
- The rest of the code isn't touched: translating is a layer on top of the API.
- Every new server text shown in the dashboard needs its phrase or template in `api/i18n.py`; if it's missing, it
  comes out in Spanish (`tests/test_i18n.py` checks the catalogue).
- Still in Spanish: the browser tab title (set at build time), Claude's explanations and screenshot summaries
  (saved already written), the ingest's technical errors and whatever arrives as-is from the sources. Up-to-date
  list in `docs/estado.md`.
- Since 15-11-2026 the same middleware does the opposite with national teams: they're stored with FotMob's English
  names and, for the dashboard in Spanish, it swaps them for their Spanish names (`names.NATIONAL_ES`).
