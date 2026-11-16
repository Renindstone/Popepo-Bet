# ADR 0006: Saved preview and weekly summary

**English** · [Español](../es/adr/0006-previa-guardada-y-resumen-semanal.md)

**Status**: accepted (2026-10-24)

## Context
The user wants to see every week the team, the player and the XI that most beat expectations: the team that went
over its corners or goals line, the one that won while having the fewest chances, the player who beat their
shots, goals or assists. For that you need to know **what was expected before the match**:

- For teams there is a yardstick: the bookmaker's odds saved before kick-off (football-data's closing 1X2 and
  each team's goals and corners lines from Pinnacle and Betano through OddsPapi, since 19-10-2026).
- For players there are no lines from any bookmaker. The only yardstick is our model, and what it expected before
  each match wasn't saved: the `prediction` table existed, but nobody wrote to it.

Redoing the analysis of a match already played doesn't work: predicted line-ups are replaced by the confirmed
ones, the active absences are today's and the model is retrained every day with that same match.

## Decision
- **Saved preview** (`services/predictions.py`): one row per match in `prediction` (unique constraint on
  `match_id`). It's written by `picks.generate`, which runs at 09:00, on every check for the confirmed line-up and
  when Today is opened. It's only rewritten if it changed and **never after kick-off**, so what remains is the last
  preview before the match, with the confirmed XI if it arrived. It stores, by side (home or away, not by team id,
  so that merging duplicate teams doesn't leave it out of date): expected goals, 1X2, the mean and the dispersion
  of each stat and the projection of every player. It takes about 6 KB per match; it's deleted with the match.
- **Summary computed when read** (`services/weekly.py`, `models/surprise.py`; `GET /week`, MCP `resumen_semana`,
  `apuestas semana`, the Week page). Nothing else is saved: if football-data's closing odds or the stats
  arrive late, the week completes itself.
- **Yardstick**, as the user asked: teams against the bookmaker (result, goals and corners; not shots on target,
  because no bookmaker prices them) and players against the model's preview.
- **Surprise score**: P(under) − P(over) with the expected distribution, from −1 to +1, so the margin counts.
  Details in `docs/modelos.md`, section 8.

## Consequences
- The player history starts on 24-10-2026: earlier weeks have no players or XI (teams do, with the saved odds).
- If the computer is off the whole day of a match and Today wasn't opened before, that match has no preview: its
  players don't count (the page's coverage says so).
- It's a summary of what happened, not a betting signal: a good week is partly luck.
- The saved preview also makes it possible to measure later the calibration of the player and stat markets with
  what was really expected before each match.
