# Handover sheet

**English** · [Español](es/traspaso.md)

Summary of what was done from 10 to 15 November 2026, so that any AI session (or the owner on another machine) can
carry on without depending on conversations that get lost. The detail lives in the linked documents; this sheet is
the index. Update it when changing PC or operating system.

## Why it exists

- **31-10 to 10-11**: the AI instructions only lived on the owner's PC (CachyOS) and were lost when it was replaced.
- **10-11**: the owner moved to Fedora. Everything was reinstalled from scratch; the previous database **was lost with
  no backup** (confirmed by the owner on 12-11): bet of the day history, CLV, logged bets, bankroll, saved Betano odds
  and previews. All of that started from zero on 11-11-2026.
- **15-11**: the owner is about to change distro again. This time there's a database backup (below).

## What was done (on `main`)

| Date | What | Where the detail is |
|---|---|---|
| 10-11 | AI instructions, skills, `DESIGN.md`, `PRODUCT.md`, `.impeccable/` and ADRs 0001-0006 recovered from the history and published | `AGENTS.md`, `docs/estado.md` (decision of 10-11) |
| 10-11 | ADR 0007 (dashboard in Spanish and English) and 0009 (reviewers' verdict) redone from the code. 0008 is still lost | `docs/adr/` |
| 10-11 | Owner's rule: **all the AI's context goes into the repository** | `AGENTS.md` |
| 10-11 | Installation on Fedora tested: the scripts work unchanged. The FotMob download was cut off and completed with a temporary service (10,604 matches with details) | `docs/instalacion.md`, `docs/estado.md` |
| 10-11 | A source under maintenance shows up in one line and the long download reports every 100 matches | commit `0fa1c50` |
| 10-11 | `DESIGN.md`, `PRODUCT.md` and the design skills brought up to date with the ES/EN selector, the verdict and "Against Pinnacle" | commit `55d0a2a` |
| 10-11 | Test `test_qualified_picks` fixed: it depended on the date | commit `55d0a2a` |
| 10-12-11 | Plan for what was missing after the PC change, with its five tasks done | `docs/superpowers/plans/2026-11-10-faltantes-tras-cambio-de-pc.md` |
| 11-11 | The screenshot driver finds the browser by itself (Brave, Chromium or Chrome), doesn't crash without matches and opens in English with `--lang en`. Clean audit in both languages except for a 19 px link | skills `run-app-apuestas` and `disenio-panel` |
| 12-11 | **UEFA Nations League** (national teams): data and analysis, no bet of the day and no player markets | `AGENTS.md` ("Conceptos que se confunden"), `docs/modelos.md` section 7 |
| 14-11 | Other XI quality indices measured: recent rating and xG+xA add nothing; the usual starters graze their margin and **don't go in** (the owner decided to wait until the end of the season) | `docs/modelos.md` section 7, `experimentos/validacion/calidad_once.py` |
| 15-11 | **The PC moved to Windows 11, without WSL.** The 15-11 backup restored (27,791 matches, 1.08 M odds, 461 saved bets), plus the model and the cache. `db.sh`, `instalar.sh` and `arrancar.sh` work in Git Bash; it's started with `scripts/arrancar.sh` (nothing starts by itself at boot) | `docs/instalacion.md` ("Windows without WSL"), `docs/estado.md` |

## What the owner asked and the short answer (14-11)

Can the bet of the day be improved now, or do we have to wait for data? Both. Raising the hit rate isn't the goal:
demanding more probability only picks lower odds. What counts is CLV, which has been accumulating since 11-11.
Analysing a single lost bet is almost always noise. What can already be measured is measured with the history
(backtest). Leads, in order: XI quality (done, doesn't go in), corners and cards against Pinnacle (around January,
when there are ~150 matches), dynamic goal strength (not very promising) and the reviewers' verdict (with ~30
counted bets of the day).

## Pending (summary; the live list is in `docs/estado.md`)

- Owner's decisions: Ollama to read screenshots or only Claude; deleting the branch `claude/wizardly-davinci-mrc9zr`;
  keys for acquaintances and starting bankroll; what ADR 0008 was about; Telegram bot.
- To measure with data: the comparison against Pinnacle and corners/cards (January), CLV, substitutes, Turkey,
  the reviewers' verdict, usual starters (end of the 2026-27 season).
- Design: a 19 px link in My bets on mobile (skill `disenio-panel`).

## Changing distro: what to keep and how to come back

What is **not** in the repository and has to be copied to an external disk or another partition before formatting:

| What | Why |
|---|---|
| `.env` | Keys (OddsPapi) and configuration. It never goes into the repository |
| `var/backups/traspaso-20261115.dump` | The full database of 15-11-2026 (24 MB): matches, odds, bets of the day since 11-11, previews |
| `var/models/latest.json` | The trained model. If it's there, `instalar.sh` skips the 3-4 hour download |
| `var/cache/` (optional, ~330 MB) | FotMob and football-data cache: avoids requesting again what was already downloaded |

To come back on the new system:

1. Install the system requirements (`docs/instalacion.md`, step 1) and clone the repository.
2. Copy `.env` to the root and `var/` (with `backups/`, `models/` and, if it was kept, `cache/`) into the project.
3. `scripts/instalar.sh`: creates the environment and an empty database; with the model in place it doesn't download the history.
4. Restore the backup onto that empty database:

   ```bash
   pg_restore --clean --if-exists --no-owner -d "$(grep '^APUESTAS_DATABASE_URL=' .env | cut -d= -f2- | sed 's#+psycopg##')" var/backups/traspaso-20261115.dump
   ```

   On Windows without WSL (Git Bash), first: `export PATH="/c/Program Files/PostgreSQL/18/bin:$PATH"`, and in step 5
   `scripts/arrancar.sh` instead of `install-services.sh` and `loginctl` (see `docs/instalacion.md`).

5. `.venv/bin/alembic upgrade head`, `scripts/install-services.sh --with-web` and `loginctl enable-linger "$USER"`.
6. Check: `systemctl --user is-active apuestas-db apuestas-worker apuestas-api apuestas-web`, the dashboard at
   `http://localhost:3000` and `.venv/bin/pytest`. The worker catches up by itself the days the PC was off.

If the backup is lost, `scripts/instalar.sh` rebuilds everything from the public sources (3-4 hours), but what's your
own (bets, CLV, previews, Betano odds) starts again from zero.
