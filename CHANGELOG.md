# Changelog

All notable changes to Popepo-Bet. A new version is cut when a big change lands (a new league or competition, a model change justified with the backtest, a new dashboard page or a new way to install or use it); small fixes go under **Unreleased** until then. Dates are day-month-year, as in the rest of the documentation. The format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/) and the numbers follow [Semantic Versioning](https://semver.org/) (still 0.x: anything can change).

Versions up to 0.8.0 were reconstructed on 16-11-2026 from the git history and `docs/estado.md`; they weren't tagged at the time. From now on, each version gets a git tag (`v0.8.0`…).

## [Unreleased]

### Changed
- **Quick install**: the first install takes about 1 hour instead of 3-4 (or more). It still downloads the results and closing odds of the whole history, but FotMob's details only for the 1,500 most recent matches; the worker downloads the rest in the background, 200 an hour (before, 400 a night), about 2-3 days with the PC on.
- Measured whether a team with a Champions League match within 4 days scores less in the league: it doesn't (goals 0.987 ± 0.07 of what the model expected, 594 matches), so the model doesn't change (`experimentos/validacion/carga.py`, `docs/modelos.md` section 3).

## [0.9.0] - 21-11-2026

### Added
- **Pinnacle as the reference in more goals markets**: team goals, both teams to score and the European handicap (Pinnacle's own lines) and double chance and draw no bet (its 1X2) are blended 25/75 with Pinnacle, like 1X2, over/under and Asian handicap already were. Before, they went on the model alone: on 21-11 the bet of the day (Roma under 2.5 goals against Parma, +22.7 % value) came only from the model seeing fewer Roma goals than Pinnacle; blended, it has no value. `apuestas backtest` now gives the log-loss of team goals and both teams to score (`logloss_goles_equipo`): blend 0.5432 against the model's 0.5442 (−0.0010 ± 0.0008, 5,149 matches). Details in `docs/modelos.md`, section 6.
- **The betting table** ([ADR 0010](docs/adr/0010-mesa-de-apostadores.md)): below the bet of the day, seven Claude agents with bettor personalities (the Cautious One, the Odds Hunter, the Statistician, the Sceptic, the Reporter, the Streak Rider and the Contrarian) vote yes or no in two rounds, after For and Against bring the news. The result is "Approved by the agents" (2/3 of the weighted vote), "Partly approved" (more than half) or "Rejected by the agents", with each vote's weight and reason in Spanish and English. Each weight moves 5 % per unit the vote would have won or lost (a no, the other way round), between ×0.5 and ×2. It's an opinion: it doesn't change the model's numbers.

### Fixed
- On Windows, `claude -p` started without its prompt when the prompt had a letter outside cp1252 (a "ć" in a player's name in the news): Python wrote stdin in cp1252, the thread that writes it died, and Claude waited 3 s with no data ("no stdin data received"). That's why the seven agents of the table failed on 20-11. The prompt now always goes in UTF-8 through one shared call (`capture_engines.run_claude`), also for the "Why it failed" notes and the Claude screenshot engine, which had the same bug (a team like Gençlerbirliği would have broken them).
- When the table can't vote, the dashboard shows a short notice instead of the raw error of the seven agents; the detail stays in the worker's log.
- The table started up to 5 minutes late: its task ran in the same minute as the line-up search, so it looked before the line-up was confirmed and waited for its next turn. It now runs 2 minutes after each line-up search, and meanwhile the dashboard says "starts voting in a few minutes" instead of "will vote once the lineup is out" (21-11, Parma vs Roma).

### Changed
- The table replaces the Judge of the reviewers' verdict (ADR 0009). At most 2 reviews a day (it was 3) and, without a confirmed line-up, 40 minutes before kick-off (it was 30). New table `review_vote`; `pick_review.word` and `motives` removed.

### Security
- Next.js 16.4.2 → 16.4.6 (and `eslint-config-next`), which fixes two moderate cache leaks across root params with `'use cache'` (GHSA-vc7v-qv4w-wrv8, GHSA-mfr8-8qww-v76h). The dashboard didn't use `'use cache'`, `unstable_cache()` or root params, so it wasn't exposed. The remaining `npm audit` warnings (`minimatch` through `typescript-eslint`) only affect the linter.

### Removed
- **Understat**, down since 3-11-2026. The model doesn't change: since 2026-27 football-data brings xG for the eight leagues and it's averaged with FotMob's; older matches keep Understat's xG.

### Changed
- The README screenshots show the dashboard in English (`docs/img/`), with a new one of the Surprises radar; the Spanish ones moved to `docs/img/es/` for `README.es.md`.
- The screenshot driver finds Brave, Chrome or Edge on Windows.

## [0.8.0] - 16-11-2026

### Added
- **Windows without WSL**: `scripts/instalar.sh`, `scripts/db.sh` and `scripts/arrancar.sh` work from Git Bash (Python 3.14 through `py`, `.venv/Scripts`, a database without a Unix socket). Tested on Windows 11.
- The `apuestas` MCP server starts on any system through `scripts/mcp.mjs` (Node.js), which finds `apuestas` or `apuestas.exe`.
- Handover sheet (`docs/traspaso.md`) with what to keep and how to restore the database on a new machine.
- `CHANGELOG.md` (this file).

### Changed
- **Documentation in English first**: `README.md`, `web/README.md` and everything in `docs/` (including the ADRs) are in English; the Spanish versions are kept in `README.es.md`, `web/README.es.md` and `docs/es/`, linked from a language selector at the top of each one.
- The dashboard in Spanish shows national teams with their Spanish names ("Islas Feroe", "Alemania"), also inside bet labels; they're still stored with FotMob's English names and found by either name.

## [0.7.0] - 12-11-2026

### Added
- **UEFA Nations League** (national teams, leagues A to D): matches, analysis, odds from Betano and Pinnacle, Evaluate odds, API, MCP and bot. No bet of the day and no player markets, because there are no free historical odds to measure the model against the bookmakers. The European World Cup qualifiers, the 2026 World Cup and Euro 2024 are downloaded as history.
- The screenshot driver finds the browser by itself and can audit the dashboard in English.

### Changed
- The AI instructions, skills, design context (`DESIGN.md`, `PRODUCT.md`, `.impeccable/`) and ADRs are back in the repository; ADRs 0007 and 0009 were rebuilt from the code.
- A source under maintenance is reported in one line and the long first download reports progress every 100 matches.

## [0.6.0] - 07-11-2026

### Added
- **Reviewers' verdict**: three separate Claude roles (For, Against and Judge) leave "Bet", "Doubtful" or "Better not" below the bet of the day once the line-up is confirmed. It's an opinion: it doesn't change the probability or the pick.

### Changed
- The bet of the day and the value lists only show bets with a probability of **60 % or more**.
- Quarter lines (Asian handicap and over/under goals of .25 and .75) are no longer offered, because the owner's bookmakers don't take them; Pinnacle's are still used as a reference.
- A price not seen in the last 30 hours no longer counts.

## [0.5.0] - 31-10-2026

### Added
- **Dashboard in Spanish and English** (ES / EN switch), with the API's texts translated too.
- MIT license and a README with screenshots and an English section.
- Tapping the bet of the day opens Evaluate odds ready to log it; Evaluate odds picks the league first and then the match.

### Changed
- The bet of the day record counts **one per day**: the one with the highest value × confidence among those that were the bet of the day.

## [0.4.0] - 30-10-2026

### Added
- **Portugal, Belgium and Turkey** as full leagues (FotMob details, model, bet of the day, Betano and Pinnacle odds).
- **Surprises** page: team, player and XI of the week and the month, a radar of teams on a hot or cold streak, warnings on bets and "Why it failed" with an explanation by Claude; per-user AI switch.
- **Against Pinnacle**: a model-free comparison of Betano prices with Pinnacle's fair odds.
- **Offsides** as a new model stat, **derbies and rivalries** (more fouls and cards), each team's schedule and unusual-starter labels.
- Only current odds are used: each download records when each price was last seen.

### Changed
- Per-league home advantage, each stat's own total dispersion, stat handicaps with the correlation between teams, fouls with their league's recent level and player props conditional on playing — each one justified with the backtest (`docs/modelos.md`).
- Quarter-line value discounts half refunds; the bet counters measure what was announced.

## [0.3.0] - 28-10-2026

### Added
- **Saved preview** of what the model expected before each match, and the **Week** page (team, player and XI of the week).
- **CLV** of the bets that clear the threshold against Pinnacle's fair odds, with a Pinnacle download shortly before kick-off.
- Manual sync button in Data.
- Installation guide by system (Linux, Mac and Windows with WSL) and a one-command installer.

### Changed
- **Dashboard redesign** as a "sports newspaper front page".
- The worker only runs from 05:00 to 20:00 and waits for internet before downloading.

## [0.2.0] - 22-10-2026

### Added
- **Serie A and Ligue 1** as full leagues.
- Bets that clear the threshold are saved, settled and counted, and the value list can be sorted.
- Line-ups on the pitch, team crests, tabs on the match page and on Today.
- Screenshots read by a **local AI** (Ollama); Betano odds in Evaluate odds; bet slip with Bet Builders and accumulators; logging bets from a screenshot.
- Player markets: goal or assist, assists and players inside Bet Builders.
- A reproducible model audit with public data (`docs/auditoria-modelo.md`).

### Changed
- Shots and corners guided by the goals model's strength and split by the bookmaker's 1X2; each league's recent level in shots and cards; player shots, cards and minutes as a share of their team's.
- Only FotMob's official XI counts as confirmed.
- A host that doesn't connect is skipped for 30 minutes and Data shows why.

## [0.1.0] - 19-10-2026

### Added
- First version: data from football-data, FotMob and Understat for the Premier League, Bundesliga, LaLiga and Champions League; team strength with market-implied ratings; Dixon-Coles goals and negative binomial stats; bet of the day; walk-forward backtest; REST API, MCP server, Telegram bot and web dashboard.
- Screenshots read by Claude through MCP, OddsPapi for Betano and Pinnacle odds, settlement after each match and prudence rules for teams and stats without enough data.

