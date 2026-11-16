# ADR 0009: Reviewers' verdict

**English** · [Español](../es/adr/0009-veredicto-de-los-revisores.md)

**Status**: accepted (2026-11-06). Rebuilt on 10-11-2026 from the code, the commits of 6 and 7-11 and
`docs/estado.md`: the original only lived on the owner's PC and was lost.

## Context
The owner doubts some bets of the day for two recurring reasons:

- **Confidence.** Their personal rule is to bet only if the "confidence" figure on the card reaches 80 %.
- **Going against a team on a streak.** The Surprises radar isn't enough: by the match date it didn't flag PSG
  against Villarreal, who arrived with 5 wins in 5 matches.

They also bet after seeing the line-up, and before that the confidence almost never reaches 80 %. They wanted a
second opinion bringing together news, line-up, form and those two figures, without the AI being able to make up
or change the numbers.

## Decision
- **Three separate Claude roles** (not models from another company; Sonnet with high effort,
  `verdict_cli_model` and `verdict_effort`), each in its own isolated `claude -p` (`ai_notes.claude_command`:
  no files or terminal, an empty folder, the project's MCP in engine mode):
  - **For** and **Against** can search and read the news, and neither sees the other's text, so they don't
    influence each other. If a reviewer also writes the other's part, it fails: the verdict never comes from a
    single reviewer.
  - **Judge**, with no internet: reads both texts as data (not as instructions) and leaves "Bet", "Doubtful" or
    "Better not" with 2 to 4 reasons. That way a news page can't give it orders directly.
  - MCP tools `datos_veredicto`, `guardar_revisor` and `guardar_veredicto`, which only exist in the engine's MCP.
    Texts that make promises ("safe bet", "no risk", "guaranteed") are rejected.
- **The code provides the numbers.** The confidence against 80 % (`verdict_min_confidence`) and the streak (3
  wins in a row or 4 of the last 5, in all competitions, for the team the bet goes against) are computed in
  `services/verdict.py` and saved in the review's `numbers` copy. The judge can't use the labels "Confidence" or
  "Streak": the system adds those reasons.
- **When it's written.** The worker's `job_verdict` task, every 5 minutes and separate from bet generation (a
  failure here doesn't touch it). The bet of the day is reviewed when its line-up is confirmed or, if it doesn't
  arrive, 30 minutes before the match. There's no morning review: it would spend the subscription on something
  the owner doesn't use. At most 3 a day, counting the discarded ones that already spent the subscription, and
  only if some user of the engines has the AI switched on. Without a confirmed XI, one is enough; another is only
  worth it with the real line-up.
- **Discards and retries.** If the bet changes or the match kicks off halfway through, the review is discarded. If
  a role is missing, it's retried once and otherwise there's no verdict. When the worker starts, the ones that
  were cut off go back to the queue.
- **What's shown** (`GET /picks/{pick_id}/review`, `verdict.for_user`; option A of three mock-ups): below the bet
  of the day on Today, the word and its reasons in view and the discussion folded. Today shows the current
  confidence and warns if it crossed 80 % or if the odds moved more than 5 % since the review; past days are shown
  as they were reviewed. With the AI switched off nothing is written or shown.

## Consequences
- **It's an opinion, not a calculation.** It doesn't change the probability, the confidence, the threshold or
  which bet is picked. The decision is still the owner's, and the dashboard says so.
- It uses the PC's Claude subscription: about 9 runs a day at most (3 reviews × 3 roles), plus retries. How long a
  real review takes and how much it uses still has to be measured.
- **Not measured yet.** Every verdict is saved to check whether "Better not" really loses more than "Bet"
  (`experimentos/validacion/veredicto.py`). Until there are about 30 counted bets of the day it isn't used for
  anything automatic, and using it that way needs the owner's OK.
