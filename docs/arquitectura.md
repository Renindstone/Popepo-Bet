# Architecture

**English** · [Español](es/arquitectura.md)

**Modular monolith + worker.** A single Python package (`src/apuestas`) with modules that have clear responsibilities, and three processes that use it: the worker (scheduled tasks), the API/MCP (queries) and the bot.

```
Free sources                           src/apuestas/
────────────                           ─────────────
football-data.co.uk ─┐   ingest/      polite downloading (disk cache, pacing, retries, pause for hosts that are down)
FotMob (Opta)        ├─► store.py     entity resolution across sources + stats validation
OddsPapi (optional) ─┘   pipeline.py  ingest order and frequency
                              │
                              ▼
                    PostgreSQL (own cluster, port 5433)
                              │
         ┌────────────────────┼─────────────────────────────┐
         ▼                    ▼                             ▼
   models/               features/                    archive/
   ratings (att/def)     lineup (XI vs usual)         hot/warm/cold tiers
   distributions         context (rest,               season summaries
   fitting (bundle)      rotation, difficulty)        Parquet + DuckDB
         └──────────┬─────────┘
                    ▼
   services/  analysis (full match) · picks (bet of the day, settlement) · predictions (preview) · weekly (week and month) · radar · failure (why it failed) · ai_notes (Claude) · verdict (reviewers' verdict) · compare (Betano against Pinnacle) · rivalries (derbies)
              tracker (users, bets, bankroll) · queries (shared layer)
                    │
      ┌─────────────┼──────────────┬───────────────┐
      ▼             ▼              ▼               ▼
  mcp_server/    api/ (FastAPI)  bot/ (Telegram)  jobs/ (APScheduler worker)
  Claude and     /docs           alerts and        05:30 results + retrain
  other users'                   queries           09:00 bet of the day
  agents                                           every 20' line-ups
```

The **web dashboard** (`web/`, Next.js + ECharts) is one more interface on top of `api/`: the browser calls the REST API (CORS open only to `localhost:3000`) and it has no betting logic of its own.

**Dashboard languages** (Spanish and English, [ADR 0007](adr/0007-panel-en-espanol-e-ingles.md)): every dashboard text carries both versions where it's used (`tr("Hoy", "Today")`, `web/src/lib/i18n.tsx`); switching the selector remounts the dashboard. The dashboard sends `Accept-Language` with every request and, if it's English, an API middleware (`api/i18n.py`) translates the texts of the JSON response with a catalogue of fixed phrases and templates. If it's Spanish, the same middleware only swaps the national team names (stored in English, as FotMob gives them) for their Spanish names (`names.NATIONAL_ES`). The services, the database, the bot and the MCP stay in Spanish; the values the dashboard uses as keys ("APOSTAR", "con valor", "racha", the difficulty levels) aren't translated in the API but in the dashboard.

**Saved preview and weekly summary** (ADR 0006): `picks.generate` saves in `prediction` what the model expected from each match (one row per match, the last one before kick-off and never after; `services/predictions.py`). `services/weekly.py` compares each week what happened with the bookmaker (teams) and with that preview (players), when it's read: `GET /week`, MCP `resumen_semana`, `apuestas semana` and the Surprises page.

**Surprises** (since 29-10-2026): `weekly.score_range` scores any date range, so the month is 4 weeks. `services/radar.py` takes from the last 28 days the teams on a hot or cold streak and the players on a hot streak, with a 5-minute cache, and puts its warnings in `picks.generate`, `/matches` and the match analysis (`alerts`); they don't touch the probability or the threshold. `services/failure.py` compares the preview with what happened in a lost bet of the day (`GET /picks/{id}/failure`). `services/ai_notes.py` writes the explanation into `ai_note` with `claude -p` (the PC's subscription, isolated like the screenshot engine but with WebSearch and WebFetch): `settle_all` requests it when the bet of the day loses and the worker's `notas_ia` task writes it (minutes 5, 25 and 45), or the API does when "Investigate with Claude" is pressed (`POST /radar/investigate`, owner only). `guardar_explicacion` only exists in the engine's MCP (`APUESTAS_MCP_ENGINE`). Each user has their own AI switch (`app_user.ai_enabled`, `GET/PUT /me`).

**Bets that clear the threshold:** every value bet of a match that hasn't started yet is saved in `pick` (`picks.generate`) and updated on every recalculation; `pick.qualifies` says whether it clears the bet of the day's threshold (`picks.qualifies`: value, probability, confidence, odds range and, for now, only goals markets). The analysis shown is the last one before the match: if it stops having value it's withdrawn (`status = "withdrawn"`) and if it stops clearing the threshold it's unmarked; if it gets it back the same day, the same row is reopened. But the counters measure **what was announced** (since 29-10-2026): the first time a bet clears the threshold its odds, probability and value are frozen (`announced_*`), and `was_pick_of_day` remembers whether it ever was the bet of the day. Withdrawn bets that were announced are settled anyway and count. Settlement is the usual one (`picks.settle_all`, which isolates each bet so a broken one doesn't stop the others), and `GET /picks/qualified` gives their hits since the start and those of the last days. `picks.generate` takes a PostgreSQL lock per day (`pg_advisory_xact_lock`) so the worker and the API don't compute it at the same time.

**The betting table** (reviewers' verdict since 7-11-2026, [ADR 0009](adr/0009-veredicto-de-los-revisores.md); the table since 19-11-2026, [ADR 0010](adr/0010-mesa-de-apostadores.md)): the worker's `job_verdict` task runs every 5 minutes (`verdict.process_due`). It creates a row in `pick_review` for today's bet of the day when its line-up is confirmed, or 40 minutes before kick-off if it doesn't arrive, with a copy of the numbers and of the agents' weights. There are at most 2 a day, and only if someone among the engines has the AI switched on. Then it launches isolated `claude -p` runs (`ai_notes.claude_command`, Sonnet):
- For and Against (high effort) can read the news, and neither sees the other's text.
- Seven agents with a bettor personality (`verdict.AGENTS`, medium effort, no internet) read both texts as data and vote yes or no in two rounds, 4 at a time (`PARALLEL`): alone in round 1, and after reading the others in round 2, which is the one that counts. Each one runs with its seat (`APUESTAS_MCP_AGENT`) in its MCP's environment, so it can only vote for itself. The votes go to `review_vote`.

The MCP tools `datos_veredicto`, `guardar_revisor` and `guardar_voto` only exist in the engine's MCP. It only sees its own tools and the notes' tools.

If the bet changes or the match kicks off halfway through, the review is discarded. If a reporter or a vote is missing, it's retried once (only what's missing) and otherwise there's no verdict. The confidence against 80 % and the streak (3 wins in a row or 4 of 5 for the team being bet against) are computed by the code and saved in the `numbers` copy. The result (`verdict.tally`) is the yes share with weights: approved from 2/3, partly approved above half. The weights (`verdict.weights`) are recomputed from the settled, counted bets of the day: 5 % per unit each vote would have won or lost (a no, the other way round), between ×0.5 and ×2.

The dashboard reads it with `GET /picks/{pick_id}/review` (`verdict.for_user`), and `experimentos/validacion/veredicto.py` measures the hits per result and prints the weights.

**Logged accumulators:** a bet with `market = "combo"` in `user_bet`, whose match is the one that ends last, and its selections in `user_bet_leg`. Settlement (`picks.settle_all` and `betting.settlement.combo_profit`) resolves each selection and the accumulator: one lost is enough to lose it; a voided one divides its odds out of the total.

**Who is local:** the API only serves without a key the requests that come from the machine itself **without** proxy or tunnel headers (`X-Forwarded-For`, `CF-Connecting-IP`…). Everything else needs `X-API-Key`.

**Odds screenshots** (`services/captures.py`, `services/capture_engines.py`): the dashboard uploads the image to the API. An API thread launches Claude Code (`claude -p`), isolated and with the project's MCP server. Claude reads the image with `ver_captura`, sends the odds to `evaluar_captura` (evaluated by the same model as `evaluar_cuota`) and saves a summary. See [ADR 0005](adr/0005-capturas-con-ia.md).

## Daily flow (Lima time)

1. **05:30**: yesterday's results (FotMob, football-data), details of played matches, merging of duplicate teams, settlement of picks and bets, retraining (`var/models/latest.json`).
2. **08:30**: details of the next 4 days (predicted line-up, absences, referee), odds and, if there's a key, Betano and Pinnacle through OddsPapi.
3. **09:00**: bet of the day (goals markets only) → Telegram.
4. **70, 50, 35, 20 and 10 minutes before each match** of the eight leagues, the Champions League and the Nations League (the task runs every 5 min; not the Europa League or the Conference, because their line-ups aren't used): if it doesn't have a confirmed line-up yet (only FotMob's official XI counts, not the predicted one or the last starting XI), it's downloaded from FotMob, recalculated and a warning is sent if the bet of the day changes. FotMob usually publishes it an hour before; the 50-minute check leaves room if it's late.
5. **15 minutes before each match with open bets that clear the threshold** (the task runs every 5 min): Pinnacle through OddsPapi for those competitions, the CLV reference. At most 3 downloads a day (`APUESTAS_ODDSPAPI_CLOSING_PER_DAY`); the rest keep the last saved price.
6. **At :15 and :45**: if a match started more than 3 hours ago and something is pending, its result is downloaded and the picks and bets are settled (with their CLV against Pinnacle's fair odds or the closing ones; see `docs/modelos.md`, section 6).
7. **Every 3 hours (:10)**: bet365 and Betfair odds for upcoming matches (football-data's `fixtures.csv`).
8. **02:00**: download of pending historical details (400 per night).
9. **Monday 04:00**: storage tiers (summary and archive of closed seasons).

**Worker hours:** it only runs from 05:00 to 20:00: at 20:00 `apuestas-worker-stop.timer` stops it and at 05:00 `apuestas-worker-start.timer` starts it; outside those hours it doesn't start even when the PC is switched on (since 2026-10-26). That way it doesn't use resources at night; the 02:00 tasks are caught up on start.

**If the computer was off** at the time of a daily task (05:30, 08:30, 09:00, 02:00 or the Monday one), the worker runs it on start, in that order. The time of each one's last success is saved in `var/worker_state.json`. The bet of the day is only caught up until 12 hours after 09:00; the others, until 20 hours. **If it was suspended**, the late task runs on wake-up if no more than an hour has passed.

**If there's no internet** (when the computer starts the network takes a while; on 23-10-2026 the catch-up started without it and every source failed): the tasks that download wait until FotMob's or football-data's name resolves (`scheduler.network_ready`, without making requests). The daily ones wait up to 10 minutes; if there's still none, they aren't marked as done and the catch-up tries again after 15, without computing the bet of the day with old data. The periodic ones (line-ups, settlement, odds) skip that round. A name failure doesn't mark the host as down (`ingest/http.py`), and a task never runs twice at the same time.

## Principles

- **The model computes the numbers**; the AI agent interprets, explains and adds qualitative information (for example, it logs absences read in the news with `registrar_baja`).
- **No source is essential**: each task is logged in `ingestion_run` and a failure doesn't stop the others.
- **Anti-bot protections are not bypassed**: if a source blocks (SofaScore does), it's dropped.
- **No tuning without evidence**: the parameters (xG weight, half-life, blend with the market) were chosen with the backtest. The line-up adjustments use conservative values until there are real picks to calibrate them with.
