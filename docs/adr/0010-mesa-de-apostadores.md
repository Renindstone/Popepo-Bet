# ADR 0010: The betting table (weighted vote on the bet of the day)

**English** · [Español](../es/adr/0010-mesa-de-apostadores.md)

**Status**: accepted (2026-11-19). Replaces the Judge of [ADR 0009](0009-veredicto-de-los-revisores.md); the rest of
ADR 0009 (For and Against, when it runs, the numbers written by the code) still applies.

## Context
The owner wanted several bettor personalities to talk about the bet of the day and vote yes or no, with the result in
plain sight: "Approved by the agents", "Partly approved" or "Rejected by the agents". He also wanted the vote of
whoever gets it right to weigh more over time, up to counting as two agents.

The reviewers' verdict (ADR 0009) already had For and Against reading the news and a Judge writing "Bet", "Doubtful"
or "Better not". It had never run on the current PC: the database starts on 12-11 and has no reviews.

## Decision
- **The table replaces the Judge.** For and Against keep bringing the news (they are the only ones with internet and
  they don't vote). Then seven Claude agents without internet read `datos_veredicto` and both texts as data, and vote:
  - The owner's three: **The Cautious One** (yes only with a model probability of 70 % or more, confidence at the
    owner's 80 % rule, a confirmed line-up, no streak against and no settlement traps), **The Odds Hunter** (yes when
    the bookmaker clearly pays more than the fair price and the other books, even with a modest probability) and
    **The Statistician** (yes when the numbers hold up in detail).
  - Four more, proposed and approved: **The Sceptic** (thinks like the bookmaker: a big edge with no reason makes him
    suspect the model is missing something), **The Reporter** (context: rotations, motivation, midweek Champions
    League), **The Streak Rider** (never against a team on a streak) and **The Contrarian** (distrusts the "obvious"
    bet on the big favourite).
- **Two rounds.** In round 1 each agent votes alone; in round 2 each one reads the others' round-1 votes and reasons
  and gives a final vote, which is the one that counts. Each reason is 1 to 3 sentences, in Spanish and in English.
- **Result.** Yes share = weight of the yes votes ÷ total weight. 2/3 or more: approved; more than half: partly
  approved; half or less: rejected (a tie is rejected, for prudence). With seven equal votes: 5+, 4, 3 or fewer.
- **Weights.** Every agent starts at ×1, capped at ×2 and floored at ×0.5. When the bet of the day settles, each final
  vote moves its weight by 5 % per unit it would have won or lost staking 1 at that price (`settlement.profit`): yes and
  it wins at 1.72, +3.6 %; yes and it loses, −5 %; **a no counts the other way round** (no and it loses, +5 %; no and it
  wins at 1.72, −3.6 %); halves count half and voids nothing. The weights are recomputed from history
  (`verdict.weights`: the counted bets of the day with their last review before kick-off) and each review stores the
  ones it was voted with.
- **Each agent can only vote in its own seat.** Its `claude -p` passes the seat to its MCP server in
  `APUESTAS_MCP_AGENT` ("agent:round"), and `guardar_voto` takes neither the agent nor the round. A text read by the
  reporters can't make an agent vote for another one or jump ahead to round 2.
- **Cost and timing.** About 16 `claude -p` runs per review (2 reporters + 7 agents × 2 rounds). The agents of each
  round run 4 at a time, with medium effort. At most 2 reviews a day (it was 3) and, without a confirmed line-up,
  40 minutes before kick-off (it was 30).
- Data: new table `review_vote`; `pick_review.weights` added; `pick_review.word` and `motives` removed (the Judge's).

## Consequences
- **It's still an opinion.** It doesn't change the probability, the confidence, the threshold or which bet is chosen,
  and the dashboard says so.
- **Flaws we accept and say out loud:** the seven agents vote on the same bet each day and read the same numbers, so
  their votes look alike; with few bets the weights mostly measure luck. Reaching ×2 needs a net +20 units on an
  agent's votes, which takes months.
- The first real run will show how long it takes and how much of the subscription it uses; nobody has measured it yet.
- `experimentos/validacion/veredicto.py` measures hits per result and prints the weights. Using the table for anything
  automatic needs about 30 counted bets of the day and the owner's OK.

## Alternatives considered
- **The table next to the old verdict:** two verdicts that can contradict each other, and twice the cost.
- **Every agent with internet:** more cost, more risk of a page giving them orders, and they would copy each other.
- **The owner's first weight rule** (only a yes changes the weight, fixed steps): an agent that always says no never
  risks anything, and an agent that says yes to everything gains weight with bets that lose money at their price.
