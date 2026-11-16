# Model audit (October 2026)

**English** · [Español](es/auditoria-modelo.md)

A review of the model with real, out-of-sample data, done between 19 and 22 October 2026 on commits `e7f58aa` and `960b1c5`. The experiments are in [`experimentos/auditoria/`](../experimentos/auditoria/) and can be repeated on any machine. The figures on this page come from there.

**The main point.** No model tested, Bayesian or machine learning, beats bet365's opening odds in 1X2. What clearly improves is the project's own model (dynamic strength, more observations, well-set dispersion), and that matters where there are no sharp odds. The only thing that gave a positive return was comparing prices across bookmakers.

## Data and method

- 62,140 matches from the 14 leagues with stats (July 2013 to September 2026), from football-data and ClubElo through xgabora's public dataset. bet365 opening odds (1X2, over/under 2.5 and Asian handicap), maximum odds of about 17 bookmakers, shots, shots on target, corners, fouls, cards and Elo.
- No xG, Pinnacle, closing odds or referee. The "with market" version of the model uses bet365's opening odds of matches already played.
- Walk-forward with the repository's code (`ratings.fit`, `market.implied_goals`, `fitting.fit_counts`) and its parameters. Test on 2021-22 to 2025-26 (23,548 matches); the new hyperparameters were chosen on 2016-21.
- Log-loss as the main metric, standard errors with a bootstrap by matchday. In the tables, "±" is one standard error.

## Goals model results

| What was tested | Log-loss difference per match (negative = better) |
| --- | --- |
| Repository with market against no-vig bet365 | +0.0069 ± 0.0006 (14 leagues), +0.0084 ± 0.0014 (3 full) |
| Fixed 25/75 blend (`W_MODEL`) against the odds alone | +0.0008 ± 0.0001 |
| Learned logistic stacking against the odds alone | −0.0001 ± 0.0002 (the model's weight comes out almost zero) |
| Dynamic Bayesian model (Kalman filter) against `ratings.fit`, goals only | −0.0047 ± 0.0007 in 1X2 and −0.0037 ± 0.0005 in over/under 2.5; wins all 5 seasons |
| Shots on target as an extra observation in the dynamic model | −0.0015 ± 0.0003 in 1X2 and −0.0027 ± 0.0003 in over/under |
| Home advantage per league against a single one for all | LaLiga −0.0024 ± 0.0010, Segunda −0.0035 ± 0.0013, Serie A −0.0012 ± 0.0005, total −0.0004 ± 0.0002 |
| Logistic calibration layer on the repository's 1X2 | −0.0005 ± 0.0002 (it fixes the too-few draws) |
| LightGBM without odds against the goals-only dynamic model | −0.0035 ± 0.0008, but 0.012 behind bet365 |
| LightGBM with odds as an input against the odds alone | +0.0022 ± 0.0005 |

The dynamic model has attack and defence per team with a random walk (variance of 0.00001 per day and an extra 0.01 over the summer break), and a goal level and home advantage per league that also move. It's updated with each match's Poisson likelihood and gives the variance of each prediction. It runs in 17 seconds for 62,000 matches (`experimentos/auditoria/ekf.py`).

Other things that were seen. The repository with market came up short on goals in 10 of 14 leagues (over 2.5 at 51.0 % against 52.1 % real). In the middle bands of draw probability it predicts 25.9 % and 27.6 % and 27.3 % and 29.3 % happened.

## Count results

**The changes of 21 and 22 October work.** Repeated with bet365's *opening* odds (the repository's backtest uses the closing ones, which already know the line-ups), the per-team improvements are almost the same as `docs/modelos.md` says.

| Change | Shots | On target | Corners | Fouls | Cards |
| --- | --- | --- | --- | --- | --- |
| Shrinkage by matches and goals-model strength (21-10), per team | +0.0236 ± 0.0015 | +0.0205 ± 0.0013 | +0.0304 ± 0.0018 | +0.0165 ± 0.0015 | +0.0178 ± 0.0014 |
| Split by the bookmaker's opening 1X2 (22-10), per team | +0.0151 ± 0.0012 | +0.0100 ± 0.0009 | +0.0075 ± 0.0007 | n/a | n/a |
| Total dispersion calibrated out of sample, on the current model | +0.0045 ± 0.0008 | −0.0003 ± 0.0003 | +0.0057 ± 0.0008 | +0.0039 ± 0.0006 | +0.0060 ± 0.0011 |
| Dynamic league level (45 days of out-of-sample errors), per team | +0.0024 ± 0.0007 | −0.0005 ± 0.0007 | −0.0014 ± 0.0004 | +0.0060 ± 0.0009 | +0.0023 ± 0.0008 |

Log-likelihood per match, positive = better.

**What remains open.** The total is computed as if the two teams were independent (`MatchModel._stat_pmfs`, convolution). In the data, the home and away residuals correlate +0.22 in cards, −0.23 in corners and −0.22 in shots. That's why the cards total comes out too narrow (a line to which the model gives 20 % "over" happens 23 % of the time) and the corners and cards handicaps are mispriced. Calibrating the total's dispersion fixes a good part of it (row 3).

**This season's trends.** In August and September 2026 there are more shots and fewer cards. The shots model is 7.7 % short on the total and the cards one 16 % high, with data up to 3 September. It matches what `docs/estado.md` already notes. The 240-day half-life is slow to pick it up; the dynamic league level helps with shots, fouls and cards, but at the start of the season it needs a few weeks of matches.

**Corners and cards now add something.** Comparing the total with the calibrated dispersion on both sides, the earlier model didn't beat the league average in corners (−0.0058 ± 0.0019 per match, 14 leagues) or cards (−0.0020 ± 0.0020). The current one does, with corners +0.0069 ± 0.0011 and cards +0.0077 ± 0.0015 (in the 3 full leagues, +0.0117 and +0.0156). There's still no backtest against stat odds, which is what decides whether there's value.

## Betting decision

- The bets the repository's model marks as value against bet365 announced +8.5 % on average and lost 7.5 % ± 1.4 % (8,845 bets). By band of announced value (3-6 %, 6-10 %, 10-20 %, over 20 %) the real return was −8.2 %, −10.6 %, −11.6 % and +1.5 % ± 7.5 %. The announced value doesn't predict the profit.
- The bet of the day with the production rules announced +12.1 % and lost 7.2 % ± 3.9 % (969 days). Picking the maximum among many candidates selects the model's errors.
- Comparing prices was the only positive thing. With the stacking's probability (almost the market's) and the best of about 17 bookmakers, +6.1 % ± 2.6 % over 2,855 bets. That's what Kaunitz and others (2017) found, and they ended up with limited accounts. The version within the project's reach is comparing Betano with no-vig Pinnacle, with what OddsPapi already saves.

## Open bugs in the code (commit `960b1c5`)

| Bug | Where | Fix |
| --- | --- | --- |
| The value of quarter lines comes out inflated by 12 % to 16 %: it only discounts the full refund | `services/analysis.py` line 390 | Use `Outcome.ev` with the blended probability, which counts half wins and half losses |
| Double chance, draw no bet, both teams to score and European handicap use only the model | `analysis._sharp_prob` (line 326) | Invert Pinnacle's 1X2 and over/under into a matrix and derive every goals market from it (local branch `claude/precio-afilado-mercados`) |
| The saved bet is overwritten on every recalculation, so the hit counter and the CLV measure the last version and not what was announced | `picks._upsert_pick` (line 73), `qualified_picks` | Save a fixed copy when publishing and also measure the withdrawn ones |
| Fixed blend with the market | `analysis.W_MODEL` (line 24) | Learned stacking per market type, trained on previous seasons |
| Confidence as a product of hand-made factors, multiplied by the value to choose | `analysis._confidence`, `picks.score` | Probability that the value is positive, with the model's variance |
| Kelly with the probability as if it were exact | `betting/odds.py` `stake_pct` | Shrink according to the variance (Baker and McHale, 2013) |
| The "against the league average" baseline is the global average | `backtest/engine.py` lines 470 and 476 | Each league's average, home and away separately |
| Each team's count is added up as independent | `match_model._stat_pmfs` (line 108) | Total with calibrated dispersion and a beta-binomial split, or a bivariate negative binomial |
| A single home advantage for every league and cup | `models/ratings.py`, `home_adv` | Home advantage per league with shrinkage |
| Substitutes with 12 minutes on average even though the bet is voided if they don't play | `analysis.py` line 274 | Mixture of scenarios conditional on playing |
| Fixed shrinkage of 4 matches in per-90 rates and fixed dispersion of 0.15 in player shots | `analysis.py` line 268, `match_model.py` line 295 | Empirical Bayes per stat and position |

## What to implement and in what order

1. **Risk-free fixes.** Value of quarter lines, fixed copy of what was announced and per-league baseline in the backtest.
2. **Dynamic strength for goals.** The filter in `experimentos/auditoria/ekf.py` as an alternative to `ratings.fit`, with goals, xG and shots on target as observations and Pinnacle's closing odds (or OddsPapi's while football-data is down) as the market observation. Extra advantage: it doesn't drop the market after 14 days, it keeps it with growing uncertainty. It needs `apuestas backtest` with the database.
3. **Counts.** Total dispersion calibrated out of sample in all of them, and dynamic league level in shots, fouls and cards (not in corners or on target).
4. **Market and calibration.** Pinnacle matrix for every goals market, learned stacking instead of `W_MODEL` and a calibration layer for draws.
5. **Decision.** Choose by the probability of positive value, shrink value and Kelly with the variance, and a comparison of Betano against no-vig Pinnacle. Ask for a second odds snapshot close to kick-off only for matches with a bet, to have Betano's CLV.
6. **Players.** Hierarchical model with minutes as a mixture and shrinkage estimated from the data.

Each step only goes in if it improves in a paired way on a held-out season that isn't used for tuning.

## References

- Koopman and Lit, dynamic bivariate Poisson model for the Premier League: https://ideas.repec.org/p/tin/wpaper/20120099.html
- Egidi, Pauli and Torelli (2018), historical data and odds in a hierarchical Bayesian model: https://arxiv.org/abs/1802.08848
- Ley, Van de Wiele and Van Eetvelde, comparison of maximum likelihood models: https://arxiv.org/pdf/1705.09575
- Benz and López (2021), home advantage without crowds changed differently in each league: https://arxiv.org/pdf/2012.14949
- Wheatcroft (2021), predicting matches by predicting their stats: https://ar5iv.arxiv.org/html/2001.09097
- Walsh and Joshi (2024), choosing models by calibration rather than accuracy: https://researchportal.bath.ac.uk/en/publications/machine-learning-for-sports-betting-should-model-selection-be-bas/
- Baker and McHale (2013), Kelly under uncertainty: https://ideas.repec.org/a/inm/ordeca/v10y2013i3p189-199.html
- Kaunitz, Zhong and Kreiner (2017), comparing bookmakers against the consensus: https://www.technologyreview.com/2017/10/19/67760/the-secret-betting-strategy-that-beats-online-bookmakers/
