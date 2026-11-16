# ADR 0005: Odds screenshots read by an AI through MCP

**English** · [Español](../es/adr/0005-capturas-con-ia.md)

**Status**: accepted (2026-10-19)

## Context
The user sees odds on Betano or bet365 (above all props: corners, cards, shots) that don't arrive through any free source. Typing them by hand in *Evaluate odds* is slow. The idea is to upload a screenshot in the dashboard and have an AI read it.

MCP works the other way round from how it looks: it's the AI that calls the system's tools, not the system that "sends" something to the AI. That's why the website can't send the image to Claude through MCP: someone has to launch the AI.

## Decision
- **A single flow with states** (`odds_capture`): pending → processing → evaluated → ready (or error). The image is saved in `var/capturas/<user>/` and its real type is checked by its first bytes. Only PNG, JPG and WEBP up to 10 MB are accepted.
- **The AI only reads.** It sends the odds it sees to `evaluar_captura`, and the statistical model computes the probability, the expected value, the stake and the verdict with the same code as `evaluar_cuota` (`analysis.evaluate_user_odds_many`). Then the AI writes a summary with `guardar_veredicto_captura`. If it doesn't write one, the screenshot is ready anyway, with the numbers.
- **Default engine: Claude Code with the owner's subscription** (`claude -p` launched by the API in a separate thread, one screenshot at a time). It runs isolated:
  - with no tools of its own (`--tools ""`);
  - only with our MCP server (`--strict-mcp-config`);
  - with only three tools allowed (`ver_captura`, `evaluar_captura` and `guardar_veredicto_captura`), and `--permission-mode dontAsk` so everything else is refused;
  - with no settings or hooks from elsewhere: an empty working folder and `--setting-sources ""`;
  - without `ANTHROPIC_API_KEY` in the environment, so the subscription is used.

  The text in the image is treated as data, not as instructions. Cost: zero. It uses the plan's usage limit. A screenshot takes about 10 to 15 seconds.
- **Other users**: the subscription is personal, so by default the automatic engine only processes the screenshots of `APUESTAS_DEFAULT_USER`. Everyone else's stay pending, and their own agent processes them through MCP: `capturas_pendientes` → `ver_captura` → `evaluar_captura` → `guardar_veredicto_captura`.
- **`api` engine ready** (`APUESTAS_CAPTURES_ENGINE=api` + `APUESTAS_ANTHROPIC_API_KEY` + `pip install -e ".[api]"`): the same flow with the Claude API and a tool loop. It's faster and doesn't depend on this PC, but it costs money per screenshot. Each Claude Code run saves in `engine_info.api_equivalent_usd` what it would have cost through the API, to decide with data. **Not tested with a real key** (only with a mocked client in the tests).

## Extension (20-10-2026): accumulators, Bet Builders and "not evaluable"
- **New tools:**
  - `evaluar_combinada`: one block per match with its selections, the block's odds and the total.
  - `marcar_no_evaluable`: saves the reason when there's nothing to evaluate.
- **Calculation** (`MatchModel.joint_goal_prob`): several selections from the same match are combined cell by cell in the Dixon-Coles matrix. Only those that depend solely on the scoreline and aren't refunded are accepted: 1X2, double chance, both teams to score, over/under goals with a .5 line and handicaps without refund. A single selection can be from any market. Different matches are multiplied, because they're independent.
- **If the AI finishes without evaluating anything,** the screenshot becomes `no_evaluable` with its explanation, not `error`. `error` is kept for engine failures (timeout, expired Claude session…).
- **Real case that prompted it:** an accumulator of 3 Betano Bet Builders (odds 11.03) came out as "Couldn't be read". Now City + over 2.5 comes out at 44 % (−41 %) and Roma + Roma over 1.5 at 77 % (−5.6 %). PSG-Barça is marked not evaluable because of the saves and "scores or assists".

## Extension (20-10-2026, night): players in Bet Builders
- **New markets:** `player_assist` (gives an assist) and `player_goal_assist` (scores or assists), with FotMob's xA. `player_goal` accepts a line (`over 1.5` = 2 or more goals). They're settled with the player's goals and assists.
- **Calculation:** player goals and assists are combined with the scoreline by sharing each team goal among its players (`MatchModel.joint_prob`, details in `docs/modelos.md`). Corners, cards, shots and fouls inside a Bet Builder are multiplied as independent and the block is marked "approximate"; before, they left the block unevaluated.
- **Real case:** bet365's 4-match accumulator (odds 12.62) had two non-evaluable blocks, "Kane to score or assist" and "Real Madrid + Mbappé to score". Now they come out at 17 % (fair odds 5.81 against 4.30) and 53 % (1.89 against 1.43), and the whole accumulator at 2.6 % (fair 37.8): no value.

## Alternatives discarded
- **Local OCR (Tesseract)**: it's free, but fragile with the bookmakers' layouts and can't turn "Total de córners Más de 9.5" into `ou_corners/over/9.5`.
- **Sending the image in the `claude -p` prompt**: it also works, but then the AI wouldn't go through MCP, and external agents need `ver_captura` anyway.

## Consequences
- The dashboard needs the API to be running to process screenshots. If the API restarts, on start it queues again the ones left halfway.
- If the model's 1X2 is badly calibrated in a match, for example in the Champions League, where there's no sharp market to blend with, the screenshot reflects it. Claude warns about it in its summary, but the number comes from the model.

## Extension (20-10-2026, night): logging the bet from the screenshot
- `POST /captures/{id}/bet` logs one price from the screenshot (`line`) or its whole accumulator with what's already saved in it, without redoing the form in Evaluate odds. Accumulators use the same logging as the bet slip (`queries.register_combo`).
- The `evaluar_captura` and `evaluar_combinada` tools accept `importe` (the stake, if it's visible in the screenshot) to suggest it when logging.
- What was logged is saved in `engine_info.bets`, which isn't erased when the screenshot is read again or the odds are fixed, so the same bet isn't logged twice.

## Extension (21-10-2026): local engine with Ollama, by default
- **Reason:** not depending on a paid account to read screenshots.
- **Design** (`services/capture_reader.py`, `local` engine): the vision model (qwen2.5vl:7b on Ollama) **only transcribes** with a fixed JSON schema (match, market title, selection, odds, Bet Builder odds, total, stake). In a test asking it for the market codes directly it got them wrong (double chance as 1X2, skipped selections); transcribing, it copied all of them correctly. The rules in `parse_selection` turn the text into markets, `plan` decides between single prices and an accumulator (and fixes an impossible total with the product of the blocks), the model does the numbers and `summary_*` writes the summary from a template.
- **Result** with the two real screenshots Claude had read: the same selections, odds and totals (including Kane's goal or assist, Mbappé's goal and the 3-way handicap), stake read, in 4 to 7 seconds with an RX 7700 XT.
- **Fallback:** `POST /captures/{id}/process?fallback=true` reads it again with `captures_fallback_engine` (Claude Code); in the dashboard, the "Read with Claude" button.
- **Limit:** the rules cover the usual Betano and bet365 markets; an unusual market comes out as "other" (not evaluable) and is fixed by hand or with Claude.
