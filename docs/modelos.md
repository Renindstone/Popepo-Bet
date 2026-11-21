# Models and validation

**English** · [Español](es/modelos.md)

## 1. Team strength (`models/ratings.py`)

A Poisson-type multiplicative model fitted **jointly for 17 leagues**:

```
log E[home_goals] = mu + home_advantage + attack[home] - defence[away]
log E[away_goals] = mu                  + attack[away] - defence[home]
```

- **Target**: 15 % goals + 85 % xG (xG predicts better than goals; the weight was chosen with the backtest).
- **Market-implied ratings** (`models/market.py`): the closing odds of each played match (Pinnacle; if there are none, bet365), without margin, are inverted into expected goals (home, away): the two means whose Dixon-Coles matrix reproduces the 1X2 and the over/under 2.5. They enter the fit as extra observations with **weight 128** and a **14-day half-life** (`MARKET_WEIGHT`, `MARKET_HALF_LIFE`). They don't count as played matches or for overdispersion. They cover about 14,000 matches from the 14 leagues with odds (the European cups have none). In practice the rating follows the market's recent opinion, and real goals/xG only rule when recent odds are missing (for example, at the start of the season).
- **Age**: a 240-day half-life (120, 240 and 400 were tried).
- **Market age in days with matches: measured and not applied** (29-10-2026, `experimentos/validacion/mercado_jornadas.py`; `fitting.MARKET_MATCHDAYS = False`). The 14-day half-life of the closing odds also runs during the summer break, so at the start of the season they barely weigh. Counting only days with matches, the break doesn't age them. The model's 1X2 log-loss against the current one, in August-September (about 400 matches per season): with 10 days with matches, −0.0019 ± 0.0058 in 2024-25, +0.0004 ± 0.0063 in 2025-26 and −0.0017 ± 0.0058 in 2026-27; with 14 and 20, similar. Over the whole season, ±0.001. Not distinguishable: the plateau of the market's half-life (7-14 days) already held up at the start.
- **Each competition's own home advantage** (since 29-10-2026, `fitting.GOALS_HOME_L2` = 1,000 and `RatingModel.home_by_comp`). The common home advantage is fitted as always, and each competition adds a deviation shrunk towards 0 with that L2. Each league's played matches and closing odds inform it. On 2024-26: Serie A −0.066, Premier League −0.038, Ligue 1 −0.022, Bundesliga −0.010 and LaLiga +0.044 over a common advantage of 0.248 (in log home goals). Only in goals: the counts keep a single one. Measured with `experimentos/validacion/ventaja_local.py`, against a single advantage on the same backtest matches (model 1X2 log-loss, paired 95 % margin):

  | L2 | 2024-25 (to choose) | 2025-26 (test) | 2024-26 |
  | --- | --- | --- | --- |
  | 300 | −0.0005 ± 0.0013 | −0.0013 ± 0.0013 | −0.0009 ± 0.0009 |
  | **1,000** | −0.0005 ± 0.0010 | −0.0011 ± 0.0010 | −0.0008 ± 0.0007 |
  | 3,000 | −0.0003 ± 0.0006 | −0.0008 ± 0.0006 | −0.0005 ± 0.0004 |
  | 10,000 | −0.0002 ± 0.0002 | −0.0003 ± 0.0003 | −0.0003 ± 0.0002 |

  1,000 was chosen: in 2024-25 it ties with 300 and shrinks more. By league (2024-26): LaLiga −0.0021 ± 0.0028, Serie A −0.0028 ± 0.0023, Premier League −0.0006, Ligue 1 +0.0005 and Bundesliga +0.0013 ± 0.0009 (slightly worse). `apuestas backtest`: model 0.9744 → 0.9736 and blend with Pinnacle 0.9702 → 0.9700 (the same as Pinnacle). The bets: model+market 106 → 97, with CLV +2.8 % → +3.0 % and 55 % → 58 % beating the close, but return −15.8 % → −23.5 % (Asian handicap −4.5 % → −16.5 %); model only −4.0 % → −5.1 % with CLV +0.6 % → +0.9 %. With about 100 bets the return has a margin of about ±20 points: the decision is made on log-loss and CLV, which improve. `--no-home-by-league` reproduces the previous behaviour.
- **L2 regularisation**: teams with few matches (promoted sides, exotic Champions League opponents) are pulled towards the average.
- **Common scale**: Champions/Europa League matches and promotions/relegations (Championship, 2. Bundesliga, Segunda) connect the leagues. That way a promoted team or a Portuguese Champions League opponent has a comparable rating.
- **Dynamic strength (Kalman filter): measured and not applied** (29-10-2026, `experimentos/validacion/fuerza_dinamica.py`). It's the audit's alternative: each team's attack and defence with a random walk, and goal level and home advantage per competition, updated match by match with the same observation (85 % xG + 15 % goals) and with the goals implied by the closing odds as an observation of their logarithm. It was measured with the database on the same backtest matches (bet365 and Pinnacle opening odds) and with the same rho, so only the strength changes. The parameters were chosen with 2024-25 (s_mkt 0.06, q 3·10⁻⁴ per day, no extra summer noise, level per competition, promoted teams −0.3) and the honest test is 2025-26:

  | 1X2 log-loss | 2024-25 (tuned) | 2025-26 (test) | 2024-26 |
  | --- | --- | --- | --- |
  | Current model (`ratings.fit`) | 0.9708 | 0.9782 | 0.9744 |
  | Dynamic strength | 0.9692 (−0.0017 ± 0.0030) | 0.9762 (−0.0020 ± 0.0032) | 0.9726 (−0.0018 ± 0.0022) |
  | Pinnacle | 0.9639 | 0.9764 | 0.9700 |
  | bet365 | 0.9648 | 0.9763 | 0.9704 |

  It improves somewhat, but less than its margin, and is still behind the bookmakers overall. The audit found −0.0047 against the goals-only model; against the current one, which already follows the market with weight 128 and a 14-day half-life, less is left. The best comes with an almost noiseless market (small s_mkt) and a lot of volatility: the filter turns into following the closing odds, like the current model. Putting it into production would change the goals model and everything hanging from it (counts guided by strength, line-ups, market coverage), so it isn't applied with this improvement. Measure it again with another season of data.
- **Transfers**: the line-up adjustment (below) uses each player's market value and rating. A new signing enters the line-up with their quality, even if the team still has few matches with them. Transfers are detected when a player appears with another team (table `transfer`).

## 2. Goals and markets (`models/distributions.py`, `services/match_model.py`)

A **Dixon-Coles** scoreline matrix, with ρ estimated from the data. From it come 1X2, double chance, draw no bet, Asian handicap (including quarter lines, with half wins or losses), European handicap, over/under goals (total and per team) and both teams to score.

## 3. Stats: shots, on target, corners, fouls, cards and offsides

The same strength model applied to each stat (how much each team generates and how much it concedes), with a **negative binomial** distribution (overdispersion is estimated from the data). Each team's markets use their own negative binomial; the match total uses another with the mean of the two and its own dispersion (next point). Handicaps and the "winner" of each stat come from the difference between the two, with the correlation implied by the total's dispersion (next point).

- **The total's own dispersion** (since 29-10-2026, `fitting.COUNT_TOTAL_DISPERSION` and `dist.count_total_pmf`): shots 0.010, on target 0.003, corners 0.017, fouls 0.005 and cards 0 (Poisson). Before, the total was the sum of the two teams as if they were independent, but they aren't: in the 2024-26 league matches, the home and away residuals correlate −0.22 in shots and −0.19 in corners (if one attacks, the other doesn't) and +0.17 in cards (a heated match raises both). Adding them up as independent gave a total that was too wide in shots and corners. The dispersion was measured **out of sample** in the backtest: the fit's own comes out half as high in corners and made cards worse. Example: 6.0 and 4.5 expected corners (team alpha 0.07) gave a standard deviation of the total of 3.8 corners; now, 3.5. Each team's markets don't change. Figures in section 7.

- **Shrinkage towards the average in "equivalent matches"** (since 21-10-2026, `fitting.COUNT_PRIOR_MATCHES`): shots and shots on target 1, corners 5, fouls 5 and cards 10. A team with n matches (weighted by age) keeps roughly n / (n + K) of what's seen in them; league teams (25-45 matches) barely change. Before, it was a fixed L2 of 1, the same as in goals. But each match weighs in the fit as much as its mean (~1.4 goals, ~5 corners, ~12 shots), so that L2 barely shrank: it was equivalent to 0.1 matches in shots and fouls, 0.2 in corners and 0.5 in cards.

  Real case: **Aston Villa-Viking** (Champions League, 21-10-2026). Viking is Norwegian. The Norwegian league doesn't enter the model and football-data doesn't bring its corners, so there were only two of their matches with stats: 5 corners in Stuttgart and 7 against Bayern. With them, their corners attack came out at ×1.8 the average. The model expected 14.7 corners (Villa 9.1, Viking 5.6) against Pinnacle's 10.5 (7.4 and 3.0), and Today showed "Corners: over 16.5" at 10.00 with +232 % and "Viking corners: over 6.5" at 9.75 with +230 %. With the shrinkage, 11.3 (7.0 and 4.3); the rest is corrected by the prudence rule in section 6.

- **Shots, shots on target and corners guided by the goals model's strength** (since 21-10-2026, `fitting.COUNT_STRENGTH_PRIOR`). In these three stats, which depend on how much each team dominates, a team's strength is `b × goals_strength + deviation`, with `goals_strength` = attack + defence in the goals model, `b` fitted (one for generating and another for conceding) and the shrinkage only on the deviation. That way, a team with little data gets closer to what corresponds to its strength and not to the average, and the shrinkage is larger: K = 8 in shots and on target, and 20 in corners. In cards and fouls it doesn't improve (they stay as they were).

  Reason: until 21-10-2026 the leagues only crossed in these stats through the Champions League (for the Europa League and the Conference only the results were downloaded): about 14 weighted matches for the Eredivisie, 11 for the Belgian league and 2 for the Scottish one. Within a league, you only know how much each team dominates its opponents; the level of the whole league against the others was set by the shrinkage, which assumed all leagues were equally strong. That's why a team dominating a weak league came out just as dominant in the Champions League. The goals model, on the other hand, does know each league's strength well: it has the closing odds and all the European matches.

  Real case: **Betis-Feyenoord** (Champions League, 21-10-2026). The analysis gave Betis 4.3 corners and Feyenoord 5.6; Pinnacle, 5.3 and 4.1. "Feyenoord corners: over 7.5" at 9.00 came out with +108 % and the first four "Other value bets" on Today were Feyenoord corners. Now 4.9 and 4.9, and that price gives +41 % (Today's first one is a different bet). It's still far from Pinnacle: it's better, but it doesn't fully fix it (see backtest, section 7).

- **Europa League and Conference** (since 21-10-2026): their FotMob stats go into the five count models. That's about 1,020 matches since 2023-24, and they almost double the crossings between leagues: the Eredivisie goes from 13 to 27 weighted matches, the Belgian league from 10 to 18, the Greek from 4 to 17 and the Scottish from 1 to 10. Their xG, on the other hand, **doesn't go into the goals model** (`fitting.GOALS_XG_SKIP`): with it the Champions League got worse. Details in section 7.

- **The bookmaker's 1X2 moves the split of shots, on target and corners** (since 22-10-2026, `fitting.COUNT_MARKET_SHIFT` and `fitting.strength_shift`). Those three stats are guided by the goals model's strength (previous point), so they inherit its errors, and the goals model doesn't beat the market. If the bookmaker sees a team as stronger than the model does, the split of those stats moves towards it:
  1. From Pinnacle's 1X2 and over/under 2.5 (if there are none, bet365's; if not those either, Betano's) the bookmaker's expected goals are derived (`fitting.prematch_market_goals`).
  2. δ = ½ × [the bookmaker's log(home / away) − the goals model's log(home / away)], the latter already with the line-ups, so as not to count twice the absences the bookmaker also knows about. It's the strength that has to be added to the home team and subtracted from the away team for the goals model to say the same as the bookmaker.
  3. The home count is multiplied by exp(0.75 × b × δ) and the away count is divided by the same, with b the strength coefficient in that count (attack + defence, saved in the model bundle: ~0.6 in corners and shots, ~0.73 on target). Then it's re-split so that **the match total doesn't change**: the 1X2 says who dominates, not how much is played.

  Without odds from those bookmakers, everything stays as before. The analysis saves the bookmaker and δ in `count_market_shift`. The 0.75 weight is almost the best in the three stats (section 7).

  Real case: **Betis-Feyenoord** (Champions League, 21-10-2026). The goals model saw both as almost equally strong (1X2 46/22/32); Pinnacle, Betis as clear favourites (60/20/20; δ = 0.18). Corners came out 4.6-4.7 (Pinnacle 5.3-4.1); now 5.0-4.3. In the real analysis, with the line-ups, from 4.7-4.7 to 5.1-4.4, and the match's best "value" corners price goes from +30 % to +10 %.

- **Each league's recent level in shots and shots on target** (since 22-10-2026, `fitting.count_levels` and `COUNT_LEVEL_*`). The count model remembers 1,100 days with a 240-day half-life, so it takes months to notice that **a whole league** changes. And in 2026-27 it happened: there are 10-20 % more shots in almost every league, and the model came up short (section 7). On top of the model fitted as always, a level per league is added:
  1. In each league's matches over the last 400 days, with a **30-day** half-life: level = (real + K·g·m) / (expected + K·m), with m the total of an average match, **K = 10 matches** and g the same ratio with all competitions together (each league is shrunk towards what happens in all of them).
  2. Each team takes its league's level (that of its last league match); a European opponent with no league in the data takes g. In a league match, that league's level applies to both teams; in a cup, the average of the two leagues'.
  3. In the cups a **cup's own deviation** is also added, measured over what's expected already with the leagues' level, with a **120-day** half-life and **K = 30**: in the Champions League the model came up short on shots on target in the last three seasons (4 %, 8 % and 17 %), more than in its teams' leagues.

  The level doesn't change any team's strength (attack and defence are the same) or the split between the two: it raises or lowers the total, and player shots, which share out the team's (section 4), inherit it. It's saved in the model bundle (`level` per team and `cup_level` per cup) and the analysis applies it with the match's competition. In **corners** it was tried and makes things slightly worse (there's no change common to all leagues: Bundesliga +10 %, Premier League −6 %); in fouls it hasn't been validated, and cards carry it with their own parameters (below). Levels on 22-10-2026 in shots: Bundesliga ×1.12, Serie A ×1.10, LaLiga ×1.07, Ligue 1 ×1.06, Premier League ×1.05; on target: ×1.12, ×1.11, ×1.07, ×1.06 and ×0.99; Champions League deviation on target, ×1.03.

  Real case (analysis of 22-10-2026, weekend matches): **Stuttgart-Gladbach**, shots 19.7-10.2 → 22.0-11.4 and on target 8.1-3.3 → 9.0-3.7, and Demirović from 3.08 to 3.44 shots; **Torino-Monza**, 13.7-11.7 → 15.0-12.8; **Ipswich-Nottingham Forest**, 11.9-14.4 → 12.5-15.1 (on target the same: in the Premier League it doesn't go up). Corners don't change.

- **Referee**: factor = (observed + K) / (expected + K), with K in "neutral" matches. In **fouls** it improves the prediction (K = 20). In **cards**, measured again with LaLiga and Bundesliga referees (FotMob), K = 80. It clearly helps in LaLiga and Serie A, and somewhat in the Bundesliga; in the Premier League it doesn't help. In Ligue 1 it helps above all with fouls (see backtest).
- **Stat handicaps with the correlation between the two teams** (since 29-10-2026, `dist.count_diff_dispersion`). If the total's dispersion already captures how much the two teams take from each other, the difference's comes from the variances: Var(home − away) = 2 (Var home + Var away) − Var total. Each team uses, only for the difference, the dispersion that gives that variance (no new parameters). With negative correlation (corners and shots) the difference is wider than with two independent teams; in cards, whose total is already Poisson, it doesn't change. Example: 6.0 and 4.5 corners with alpha 0.07 go from a difference standard deviation of 3.8 to 4.1. `apuestas backtest` (entry `<stat>+diferencia`, 4,734 matches from the seven leagues, 2024-26), log-likelihood of the difference per match: shots +0.0148 ± 0.0038, corners +0.0094 ± 0.0028, on target +0.0007 ± 0.0007, fouls and cards the same.
- **Offsides** (since 30-10-2026, `fitting.COUNT_STATS`, K = 10 in `COUNT_PRIOR_MATCHES`; FotMob data in `team_match_stats`, complete since 2023-24 in the eight leagues and the cups). The same count model: the "attack" is how often a team's forwards are caught offside and the "defence", how often it catches the opponent (a high line leaves the defence's figure low). The owner's idea: Barça's trap. Weekly backtest 2024-08 to 2026-10 (`experimentos/validacion/offsides.py`, 6,026 matches), against the average: match total +0.046 ± 0.009 per match (corners, +0.015) and each team +0.125 ± 0.014 (corners, +0.150); with K = 5, almost the same. The trap repeats: each team's "defence" has a correlation of +0.55 between 2024-25 and 2025-26 (being caught offside, +0.28). In 2025-26 the teams that catch the opponent the most are Barcelona (×2.52; ×3.05 the year before), Westerlo (×2.33), Aston Villa (×2.05), Athletic (×1.92), Betis (×1.81) and Manchester City (×1.70). The analysis warns when a team catches its opponent offside 1.6 times the average or more (`analysis.OFFSIDE_TRAP`). The total is the sum of the two teams: the residuals barely correlate (−0.01) and an own dispersion doesn't improve (+0.0006 ± 0.0008). Markets `ou_offsides[_home|_away]`, `ah_offsides` and `1x2_offsides`; OddsPapi doesn't bring those Betano odds, so they're evaluated by hand. They don't enter the bet of the day.
- **Derbies and rivalries** (since 30-10-2026, `core/rivalries.py`, table `rivalry`, `fitting.DERBY_FACTOR`). 46 rivalries from the eight leagues (Real Madrid-Barcelona, Liverpool-Everton, Inter-Milan, Galatasaray-Fenerbahçe…). In them the model expected fewer fouls and cards than there were, already counting the referee: with the 182 derbies from 2024-08 to 2026-10 (`experimentos/validacion/clasicos.py`), real / expected 1.084 in fouls (standardised residual +0.38 ± 0.13) and 1.252 in cards (+0.51 ± 0.15). In shots (0.98), on target (0.97), corners (1.02), goals (0.96) and offsides (1.04, against the two teams' average) they aren't distinguishable, nor are they less predictable than a normal match (the residuals' deviation is the same). That's why both teams' fouls and cards are multiplied by 1.08 and 1.25 in derbies (also player cards, which share out the team's), with the same factor for every rivalry: with 4-5 matches each, per rivalry it's noise (Barça-Madrid has 1.78 times the expected cards, Bayern-Dortmund 0.71). Honest test: with the factor of the 80 derbies of 2024-25 (1.083 and 1.196), in the 102 afterwards the total improves +0.072 ± 0.061 in fouls and +0.152 ± 0.073 in cards per match. `apuestas backtest` (entry `<stat>+clasico`, 166 derbies of 2024-26): fouls +0.064 ± 0.048 and cards +0.122 ± 0.073. The analysis also carries the rivalry's history (`rivalry`: the last 6 head-to-heads with each team's fouls, cards, shots and offsides).
- **Unusual starter: measured; the model already accounts for it** (30-10-2026, `experimentos/validacion/titulares.py` and `titulares_modelo.py`). The owner's idea: someone who hardly ever plays comes out to prove themselves and shoots more. With their shooting rate in their earlier starts of 60' or more, corrected for how much their team shot that day (about 100,000 starters since 2023), it's the other way round: those who started 8-10 of their team's previous 10 matches produce 0.98 of their rate; 3-7, 0.91; 0-2, 0.86 (on target, 0.97, 0.90 and 0.85). But the player model, which shrinks each one's share towards their position's, already captures almost all the difference: out of sample (shares fitted each month only with what came before, with the team's real minutes and shots), the unusual starter is only 5 % below the regular one, and the relative factor learned before 2025-10 (0.973 in shots, 0.966 on target) doesn't improve what came after (+0.0000 ± 0.0007 and +0.0004 ± 0.0006). No factor is applied: the dashboard flags it as a warning ("Unusual: 1 of 10", `features/lineup.recent_starts`, with a published XI). Without dates of birth in the database, young players couldn't be separated.
- **Likely plan (each team's own way of playing against big teams): measured and discarded** (30-10-2026, `experimentos/validacion/estilo.py` and `estilo_entrenador.py`). The owner's idea: Mourinho's Madrid sits back away against big teams, so its shots go down. It was measured whether each team's own deviation from what's expected against opponents in the strongest 20 % of its league (beyond its deviation in the rest) repeats. Between seasons (about 115 teams, 2024-25 against what came after), the correlation ranges from −0.13 to +0.11 in shots, on target, corners, fouls and cards, home and away, all compatible with 0, and using it as a factor makes things worse (away shots −0.021 ± 0.014, home fouls −0.028 ± 0.017). With the same coach (5,015 Premier League, Bundesliga, LaLiga and European cup matches filled in from the FotMob cache on 30-10-2026; 1,352 matches against big teams with at least 3 earlier ones under the same coach), in date order and only with what came before: with K = 5, shots −0.028 ± 0.014, corners −0.029 ± 0.015, cards −0.023 ± 0.013 and goals −0.021 ± 0.011; with K = 10 and only away, the same or worse. Each match's plan doesn't repeat measurably: the systematic part (how much each team dominates) is already captured by strength and the bookmaker's 1X2 (section 3). In Barça-Madrid on 25-10 the model expected 31.4 shots and gave 58 % to under 32.5; there were 28.
- **Fixture congestion: measured and not applied** (30-10-2026, `experimentos/validacion/carga.py`). About 12,000 team-matches from 2024-08 to 2026-10, with what the model expected from each team against what it did (league and European cup calendar; domestic cups aren't in the database). With a **small opponent between big matches** (an opponent in the weakest 40 % of its league and, 4 days or fewer before or after, a big team from the strongest 20 % or a Champions League match; 518 cases), shots (0.99), on target (0.98), corners (0.98) and goals (1.00) don't change, but cards (0.83, residual −0.25 ± 0.07) and fouls (0.95, −0.18 ± 0.09) go down. With **3 days' rest or fewer**, cards 0.94 (−0.10 ± 0.05); with **3 matches in 14 days**, on target 0.95 (−0.09 ± 0.05). With 4 or more in 14 days everything drops 4-7 %, but that's 250 cases and isn't distinguishable. Honest test (2024-25 factor applied to what came after, team log-likelihood per match): small opponent between big matches, cards +0.005 ± 0.035 and fouls +0.007 ± 0.026; little rest, cards +0.004 ± 0.007 and fouls +0.001 ± 0.007. None is distinguishable: the model doesn't use them. The analysis shows each team's previous and next opponent, whether they're big in their competition (`features/context.py`, the goals model's attack + defence against that competition's teams over the last year) and the warning "Small opponent between big matches".
- **Champions League within 4 days: measured and not applied** (21-11-2026, at the owner's request, the same `carga.py` up to 20-11-2026, 12,308 team-matches). The idea: a team whose next match is in the Champions League 4 days later or fewer eases off in the league. In those 594 league matches it scores what the model expected (goals 0.987, residual −0.02 ± 0.07; shots 0.99, on target 0.99), the same as European teams without a European match close by (1.014, 2,685). With the Europa League or the Conference next, 0.974 (393). Its opponents score a little more (1.061, +0.06 ± 0.08), not distinguishable either. Honest test (2024-25 factor applied to what came after): own goals +0.0002 ± 0.0009 and opponent's +0.0003 ± 0.0089 per match, nothing. The model doesn't use it. It's measured without the line-up, so it includes any rotation; with the confirmed XI the line-up adjustment already accounts for who plays (section 5).
- **Fouls with their league's recent level, only in leagues** (since 29-10-2026, `COUNT_LEVEL_PARAMS["fouls"]`: 60-day half-life and `leagues_only`, no level in the cups). In the cups it made things worse (section 7). Measured with `experimentos/validacion/faltas_nivel.py` (backtest 2024-08 to 2026-10, leagues and cups), against no level, log-likelihood of the fouls total with the referee factor per match in the leagues: 2024-25 +0.0033 ± 0.0028 (to choose the half-life), 2025-26 +0.0067 ± 0.0040 and 2026-27 +0.0187 ± 0.0112 (test); per team, +0.0035, +0.0057 and +0.0203. In the cups, the same. With 30 days it improves more in 2025-26 and 2026-27 (+0.0101 and +0.0259), but it was chosen with 2024-25, where they tie.
- **Each league's recent level in cards** (since 22-10-2026; the same `fitting.count_levels`, with `COUNT_LEVEL_PARAMS["cards"]`). Cards per team go down season after season in almost every league (Serie A, first half: 2.29 in 2023-24, 2.05, 2.01 and 1.68 in 2026-27; Bundesliga 2.07 → 1.75; Ligue 1 2.08 → 1.69), and the cards model, with a 240-day half-life, lags behind: it was 5 % too high in the leagues (Serie A +8 %, Champions League +8 %). They carry the shots level with two changes: **K = 20** matches (instead of 10) and, in the cups, **only the cup's level** (`cup_alone`; 120 days and K = 30), without the average of the two teams' leagues: in cards the Champions League goes its own way (in the knockouts there are far fewer), and with that average it got worse. The referee factor is fitted against the model without the level (`expected(..., level=False)`): today's level isn't valid for matches from years ago, and on average the factor is 1.00 in each league. The analysis saves the match's level in `data_quality.cards_level`. On 22-10-2026: Serie A ×0.93, Bundesliga ×0.93, Ligue 1 ×0.95, LaLiga ×1.02, Premier League ×1.03 and Champions League ×0.93. Figures in section 7.
- **Line-up**: an XI stronger than usual generates more shots and corners (attenuated effect, exponent 0.7).

## 4. Players (`services/analysis.py::_player_projections`)

Per-90' rates weighted by age (shots, on target, goals, xG, assists, xA, fouls, yellows), **shrunk towards their position's average** (equivalent to 4 matches). Expected minutes according to the line-up: confirmed starter, predicted (85 %), substitute or, if the match doesn't have a line-up yet, their minutes in their team's last matches (below, "Minutes without a line-up"). Goals, assists, shots, on target and cards are shared out from what's expected from their team in that match (below); fouls come from their per-90' rate and their minutes.

**Goals and assists: a share of the team's goals** (since 20-10-2026). For each player, what share of their team's goals they score and assist, and their xG and xA, is computed **in the minutes they played** (team goals × minutes/90 as exposure), shrunk towards their position's with about 6 team goals of weight. The player's expected goals = (½ goal share + ½ xG share) × expected minutes/90 × their team's expected goals in that match; the same with assists and xA. "Goal or assist" adds the two (a player doesn't assist themselves).

Before, per-90' rates scaled against the team's average "against an average opponent" were used. That average opponent comes from every league in the database, including second divisions and light leagues, and that's why it inflates the average of the big leagues' teams: their real goals were 78 % (Premier League), 91 % (Bundesliga) and 90 % (LaLiga) of that average. Player goals came out low for every team. Out-of-sample check (model trained before the period, Premier League, Bundesliga, LaLiga and Champions League):

| Period | Market | Expected before | Expected now | Real | Log-loss before → now |
|---|---|---|---|---|---|
| 90 days (10,969 player-matches) | Goal | 578 | 712 | 731 | 0.2012 → 0.1981 |
| | Assist | 427 | 531 | 550 | 0.1759 → 0.1732 |
| | Goal or assist | 957 | 1,170 | 1,190 | 0.2840 → 0.2788 |
| 45 days (7,618) | Goal | 390 | 482 | 530 | 0.2098 → 0.2062 |
| | Goal or assist | 647 | 793 | 869 | 0.2996 → 0.2929 |

In the last 45 days it's still 9 % short (over 90 days, 2-3 %). The same check with Serie A and Ligue 1 is in section 7 ("Serie A and Ligue 1 as full leagues"). **No player market has a backtest against odds**: this check measures that the probabilities are well calibrated, not that they beat the bookmakers.

**Shots, on target and cards: a share of the team's** (since 22-10-2026, `fitting.VOLUME_SHARE_STATS`). Like goals: for each player, what share of their team's shots, shots on target and cards (yellows + reds, as in the cards model) they produce **in the minutes they played** is computed, shrunk towards their position's with the weight of 4 of their team's matches (about 51 shots or 18 on target; in cards, 20 matches, about 40 cards, since 22-10-2026: see "Player to be booked" below). The player's expected shots = share × expected minutes/90 × their team's expected shots in that match (with line-ups, referee and the bookmaker's 1X2, section 3); the same with on target and cards. The sum of a team's players is therefore the total the model expects from the team.

Before, it was the per-90' rate × minutes × (the team's expected shots in the match / its average "against an average opponent"), the same factor that left goals short until 20-10: it's worth 0.82 on average, and player shots came out 15 % short in every league (section 7, "Serie A and Ligue 1 as full leagues"). A data detail: FotMob leaves the shots of someone who didn't shoot **empty, not 0** (for goalkeepers, 99.8 % of the rows); when computing the share it counts as 0, as the per-90' rates already did. Otherwise, the share comes out inflated (players added up to 1.6 times the team).

Out-of-sample check with the six competitions (model trained up to the cut-off day, matches with a confirmed XI over the following 90 days; team means from the count model with the referee factor; expected / real):

| Cut-off (player-matches) | Market | Before | Now | Log-loss before → now |
|---|---|---|---|---|
| 15-01-2026 (27,220) | Shots | 0.85 | **1.00** | Over 1.5: 0.3125 → 0.3032 · over 2.5: 0.1811 → 0.1747 |
| | Shots on target | 0.86 | **1.01** | Over 0.5: 0.3469 → 0.3435 |
| | Card (yes) | 0.95 | 0.97 | 0.2749 → 0.2742 |
| | Goal / assist | 0.99 / 1.00 | same | same (0.1853 for the goal) |
| 23-07-2026 (16,463) | Shots | 0.79 | 0.92 | Over 1.5: 0.3408 → 0.3291 · over 2.5: 0.2098 → 0.2024 |
| | Shots on target | 0.79 | 0.93 | Over 0.5: 0.3630 → 0.3589 |
| | Card (yes) | 0.97 | 1.02 | 0.2661 → 0.2658 |
| | Goal / assist | 0.98 / 0.97 | same | same (0.1953 for the goal) |

By competition (shots · on target · card, expected / real before → now):

| League | 15-01-2026 | 23-07-2026 |
|---|---|---|
| Premier League | 0.78 → 1.00 · 0.84 → 1.07 · 0.94 → 0.95 | 0.75 → 0.96 · 0.83 → 1.05 · 0.91 → 0.93 |
| Bundesliga | 0.86 → 1.00 · 0.85 → 0.98 · 0.91 → 0.94 | 0.73 → 0.83 · 0.74 → 0.86 · 0.99 → 1.03 |
| LaLiga | 0.85 → 0.99 · 0.85 → 0.98 · 0.90 → 0.90 | 0.84 → 0.96 · 0.83 → 0.95 · 0.94 → 0.97 |
| Serie A | 0.88 → 1.01 · 0.92 → 1.04 · 1.01 → 1.05 | 0.80 → 0.89 · 0.81 → 0.88 · 1.03 → 1.10 |
| Ligue 1 | 0.90 → 1.00 · 0.93 → 1.05 · 0.93 → 0.94 | 0.83 → 0.91 · 0.80 → 0.90 · 1.03 → 1.06 |
| Champions League | 0.79 → 0.98 · 0.73 → 0.93 · 1.04 → 1.06 | 0.77 → 0.94 · 0.73 → 0.90 · 1.03 → 1.07 |

- **The split among players is right on both dates.** Scaling each player's figure to their team's real total (to measure only the split), shots go from 0.86 to 1.01 (January) and from 0.88 to 1.02 (July), and every league ends up between 0.99 and 1.04; on target, from 0.86 to 1.01 and from 0.89 to 1.03.
- **What's missing in July comes from the team shots model**, not the player one: it expected 12.8 shots per team and there were 14.2. In the 2026-27 season there are 10-20 % more shots in every league (per team, Bundesliga 13.0 → 15.5, Serie A 12.4 → 14.6, Premier League 12.7 → 13.9; football-data and FotMob agree) and the model, with a 240-day half-life, hadn't picked it up yet. It affects the team shots markets in the same way. Since 22-10-2026 the shots model carries each league's recent level (section 3), and since the model bundle is refitted every day, player shots inherit it. This July cut-off can't see it (the model stays fixed for 91 days, without the new season); the weekly walk-forward in section 7 can: in October 2026, 14.1 expected shots per team against 14.3 real.
- **Cards**: the split was already almost right (the average-opponent factor in cards barely moved away from 1); the new approach improves the log-loss a little. What remained by league (Serie A high, LaLiga low in January) came from the team cards model and from how λ was turned into a probability: fixed on 22-10-2026 (below, "Player to be booked").
- **Alternative tried**: dividing by the team's recent real average (200-day half-life) instead of the average opponent's. The split is also right (1.00 and 1.01), but the log-loss is slightly worse in January (over 2.5 shots: 0.1756 against 0.1747) and in the Champions League it comes up short (0.92 against 0.98); in July, a tie. The team share was chosen: it's the same method as goals and follows a player who changes team well.

Real case (22-10-2026, predicted line-ups): **Arsenal-Everton**, Saka goes from 1.79 to 2.69 expected shots ("over 1.5 shots" from 51 % to 70 %) and Havertz from 1.29 to 2.07; **Aston Villa-Manchester City**, Haaland from 2.54 to 2.97 (67 % → 74 %). With the predicted line-up (only 11 starters, no bench) the sum of the listed players doesn't reach the team total: the substitutes' part is missing, since they aren't on the list.

The model bundle saves each player's share (`volume_share` and its exposure `volume_team90`; the file goes from 1.8 to 2.4 MB). It comes in when retraining (daily results task or `apuestas train`); with an older bundle the previous formula is used. Measurement: `medir_jugadores.py` in the notes of the 22-10-2026 session (not in the repository).

**Minutes without a line-up** (since 22-10-2026, `fitting.recent_minutes` and `analysis._minutes_without_lineup`). Days before the match there's no line-up at all, not even a predicted one. Before, every player in the team with at least 2 starts went in, with probability of starting = starts / matches played (at most 0.9) and no substitutes. That frequency doesn't count the matches the player didn't play: someone who plays one match in two, but always as a starter, came out almost certain to start, just like someone who went on loan to a league without data or hasn't played for months. A team's minutes added up to 1,300-1,400 instead of the 988 it really plays (11 starters of ~82' and 4.5 substitutes of ~20', 2025-26 average), and its players' goals, shots and cards 20-35 % more than what the model expects from the team.

Now each player's expected minutes are their average over their **team's last 8 matches** with player data (`RECENT_TEAM_MATCHES`), with 0 for those they didn't play, and only counting from their first match with that team: a new signing who has started 3 matches has ~90', not 3 × 90 / 8. The probability of starting is the same frequency with the starts (at most 0.9). Then they're scaled so the team adds up to 988 minutes (`TEAM_MINUTES`): those of injured or suspended players are shared among the rest, without going over what each one plays when starting. With a predicted or confirmed line-up nothing changes.

Out-of-sample check: models retrained every 7 days with the earlier data (in production, every day) and matches with a confirmed XI over the following 90 days, simulating that they didn't have a line-up yet. Without an absences list (it's only been saved since 19-10-2026; today's applied to January matches would be noise). The real figure is every player in the team in the match: those not in the projection count as 0 expected. Left out are 16 team-matches from July for teams without any player data (newly promoted and Champions League debutants, such as Coventry, Schalke, Viking or Feyenoord), who have no players either before or now.

| Cut-off | | Before | Now | With confirmed XI |
|---|---|---|---|---|
| 15-01-2026 (643 matches, 37,380 player-matches) | Minutes per team | 1,401 | 983 | 1,025 |
| | Players / team: goals · shots · cards | 1.28 · 1.31 · 1.35 | **0.99 · 0.99 · 0.94** | 1.01 · 1.01 · 0.98 |
| | Expected / real: goals · assists · shots · yellows | 1.29 · 1.32 · 1.30 · 1.45 | **0.99 · 0.99 · 0.98 · 1.01** | 1.01 · 1.02 · 1.00 · 1.05 |
| | Log-loss: goal · assist · over 1.5 shots · card | 0.1608 · 0.1301 · 0.2996 · 0.2439 | **0.1480 · 0.1225 · 0.2689 · 0.2247** | 0.1349 · 0.1143 · 0.2201 · 0.2008 |
| 23-07-2026 (386 matches, 22,619 player-matches) | Minutes per team | 1,303 | 982 | 1,027 |
| | Players / team: goals · shots · cards | 1.20 · 1.22 · 1.26 | **0.99 · 0.99 · 0.95** | 1.01 · 1.02 · 0.99 |
| | Expected / real: goals · assists · shots · yellows | 1.14 · 1.11 · 1.11 · 1.40 | **0.93 · 0.88 · 0.89 · 1.06** | 0.95 · 0.92 · 0.92 · 1.10 |
| | Log-loss: goal · assist · over 1.5 shots · card | 0.1861 · 0.1529 · 0.3751 · 0.2565 | **0.1677 · 0.1400 · 0.3255 · 0.2300** | 0.1429 · 0.1240 · 0.2411 · 0.1938 |

By competition (minutes before → now · players' goals / team's · expected / real goals and shots, in brackets with confirmed XI):

| League | 15-01-2026 | 23-07-2026 |
|---|---|---|
| Premier League | 1,384 → 984 · 1.27 → 0.99 · goals 1.47 → 1.13 (1.18) · shots 1.27 → 0.97 (1.00) | 1,298 → 983 · 1.23 → 0.99 · 1.31 → 1.04 (1.07) · 1.18 → 0.93 (0.95) |
| Bundesliga | 1,370 → 982 · 1.24 → 0.97 · 1.23 → 0.97 (0.98) · 1.27 → 0.98 (1.00) | 1,226 → 982 · 1.12 → 0.98 · 1.05 → 0.90 (0.90) · 0.99 → 0.84 (0.84) |
| LaLiga | 1,409 → 983 · 1.29 → 1.01 · 1.20 → 0.96 (0.97) · 1.26 → 0.98 (1.00) | 1,351 → 983 · 1.20 → 0.97 · 1.16 → 0.92 (0.96) · 1.17 → 0.92 (0.96) |
| Serie A | 1,443 → 983 · 1.34 → 1.00 · 1.32 → 0.97 (1.00) · 1.38 → 1.00 (1.02) | 1,362 → 982 · 1.27 → 1.01 · 1.16 → 0.91 (0.94) · 1.12 → 0.87 (0.91) |
| Ligue 1 | 1,474 → 983 · 1.35 → 0.99 · 1.43 → 1.05 (1.06) · 1.38 → 1.00 (1.01) | 1,352 → 982 · 1.24 → 1.00 · 1.25 → 1.00 (1.01) · 1.15 → 0.92 (0.94) |
| Champions League | 1,285 → 984 · 1.18 → 0.97 · 1.09 → 0.88 (0.90) · 1.20 → 0.96 (0.98) | 1,128 → 984 · 1.04 → 0.98 · 0.85 → 0.77 (0.80) · 0.97 → 0.88 (0.92) |

- **Without a line-up it's almost the same as with the confirmed XI** in the sum (0.97-1.01 of the team in goals and shots, in every league) and in calibration: what still deviates from reality (the Premier League high in goals in January, the Champions League and July short) deviates the same with the confirmed XI, so it comes from the team models (in July, the 2026-27 season's shots, above), not from the minutes. The log-loss goes down in every market and at both cut-offs; also counting only the players who appear in both versions (goal 0.2173 → 0.2158 and 0.2185 → 0.2158; over 0.5 shots 0.5829 → 0.5692 and 0.5894 → 0.5656). With the confirmed XI it's still quite a bit better: knowing who plays is worth a lot.
- **Cards, 0.94-0.95 of the team**, as with the confirmed XI (0.98): the team cards model counts reds, and the player's share only their yellows. (Since "Player to be booked", below, the share also counts the red and substitutes get a few more minutes.)
- **Window**: 4, 6, 8, 12 and 20 matches give almost the same (goal log-loss 0.1496 / 0.1483 / 0.1480 / 0.1484 / 0.1489 in January and 0.1668 / 0.1672 / 0.1677 / 0.1682 / 0.1691 in July); 8 is the best or almost at both cut-offs and is the same window as the usual XI (section 5).
- **Absences**: without a history of absences, the redistribution of an injured player's minutes can't be measured with real absences. Treating as absent those who had been playing and weren't in the squad (more than what's known before the match), the sum stays at 986 and 979 minutes and goals at 1.00 and 0.98 of the team; knowing the absences lowers the goal log-loss from 0.1480 to 0.1414 in January (with the previous rule, from 0.1608 to 0.1523, with 1,218 minutes).
- **Limitation**: a player coming back from a long injury takes a few matches to recover their minutes (on 22-10, Rubén Vargas comes out with 5' in Sevilla-Osasuna after 2 matches out of 8; before, 59'), and a new signing doesn't appear in their new team until they play with it.

Real case (26-28 October, still without line-ups; players' goals against the team's): Torino 1.42 → 1.08 (team 1.08), Sevilla 1.85 → 1.35 (1.53), Sassuolo 1.77 → 1.44 (1.35). At Lazio, Pinamonti drops from 61' to 25' (22 % → 10 % to score) and Frattesi goes up from 27' to 80'. The model bundle saves each player's `recent_minutes` and `recent_start_rate`; it comes in when retraining, and with an older bundle the previous rule is used. Measurement: `medir_minutos.py` in the notes of the 22-10-2026 session (not in the repository).

**Player to be booked** (since 22-10-2026). Two errors that cancelled out in the total, but not by league: the probability came out ~7 % low and the team cards model was 4-8 % too high (Serie A +12-17 %). Fixing the probability revealed what that compensation hid: each player's share came out too dispersed and gave too much to starters and too little to substitutes. Changes, measured together:

1. **Probability = λ** (capped at 0.95; `MatchModel._player_outcome`), not 1 − e^(−λ). FotMob records at most one yellow per player and match (the second counts as a red: `player_match_stats.yellow_cards` is always 0 or 1), so each player's share already measures the probability of being booked per card expected from their team. With 1 − e^(−λ), as if they could get several, it came out ~7 % low.
2. **It counts whether they were booked, yellow or red** (`fitting._player_volume`), just as "Player to be booked" is settled (`betting/settlement.py`, which already counted the bet as won with a straight red). Before, the share only counted yellows: the database's 658 straight reds didn't count. A second yellow counts once.
3. **More shrinkage towards their position in cards**: 20 of their team's matches (about 40 cards) instead of 4 (`analysis.VOLUME_SHARE_PRIOR_MATCHES`). With 4, starters with less than a 5 % probability were booked 55 % more than expected and those above 30 %, 35-40 % less. With 20 and 40 the log-loss is almost the same (differences of 0.0001) and better than with 10; 20 was chosen, the best in July.
4. **Substitutes count with 20 more minutes** in cards (`fitting.CARD_SUB_EXTRA_MINUTES`), when fitting their share and in the match (if they come on, 55 % of the time). Per minute, a substitute is booked 1.7-2.3 times as often as a starter in their position (2023-26: they come on at the end, when there are more cards, and play stoppage time); with 15 more minutes defenders come out even, with 20 midfielders and with 25 forwards. Without this, the starters' share comes out inflated: with the other three changes, their expected cards were 1.07 (January) and 1.11 (July) of the real ones.
5. **Each league's recent level in cards** in the team model (section 3).

Out-of-sample check with the six competitions: model trained up to the cut-off and **retrained every week** over the following 90 days (in production it's retrained daily, so each competition's level keeps up to date), matches with a confirmed XI. "Starters" are those in the confirmed XI, which is what's usually bet on; "all" includes substitutes, and someone who doesn't come on counts as not booked (when settling, it's voided). Expected / real, with real = booked yellow or red:

| Cut-off | Group | Before | Now | Log-loss before → now |
|---|---|---|---|---|
| 15-01-2026 | Starters (14,146) | 0.965 | **0.995** | 0.4166 → **0.4112** |
| | All (27,220) | 0.935 | 1.046 | 0.2805 → **0.2774** |
| | Team cards (1,286) | 1.038 | **1.011** | −1.6305 → **−1.6288** |
| 23-07-2026 | Starters (8,492) | 1.016 | **0.996** | 0.4047 → **0.3992** |
| | All (16,678) | 0.973 | 1.040 | 0.2742 → **0.2709** |
| | Team cards (772) | 1.080 | **1.003** | −1.6086 → **−1.6016** |

Starters by competition (expected / real and log-loss, before → now):

| League | 15-01-2026 | 23-07-2026 |
|---|---|---|
| Premier League | 0.95 → 0.97 · 0.4222 → 0.4207 | 0.92 → 0.92 · 0.4319 → 0.4293 |
| Bundesliga | 0.96 → 0.97 · 0.4152 → 0.4099 | 1.11 → 1.06 · 0.3891 → 0.3820 |
| LaLiga | 0.91 → 0.97 · 0.4611 → 0.4524 | 0.97 → 0.97 · 0.4447 → 0.4376 |
| Serie A | 1.05 → 1.06 · 0.3894 → 0.3828 | 1.11 → 1.05 · 0.3630 → 0.3587 |
| Ligue 1 | 0.93 → 0.97 · 0.4234 → 0.4176 | 1.03 → 0.97 · 0.3945 → 0.3861 |
| Champions League | 1.06 → 1.07 · 0.3731 → 0.3693 | 1.08 → 1.09 · 0.3806 → 0.3779 |

Team cards by competition (expected / real, before → now): January, Premier League 1.02 → 0.99, Bundesliga 1.04 → 0.99, LaLiga 0.95 → 0.96, Serie A 1.12 → 1.07, Ligue 1 1.05 → 1.03, Champions League 1.13 → 1.07; July, 0.99 → 0.94, 1.14 → 1.04, 1.02 → 0.97, 1.17 → 1.05, 1.14 → 1.02 and 1.14 → 1.09.

- **The log-loss improves in every league and at both cut-offs**, and the gap between leagues narrows (starters: from 0.91-1.06 to 0.97-1.07 in January and from 0.92-1.11 to 0.92-1.09 in July). Before, LaLiga came out low (0.91) because the two errors added up; Serie A, the Champions League and the Bundesliga in July, high, because the team model was more too-high than the probability was too-low.
- **What's left comes from the team cards model**, not the player one: starters follow the team's cards (in July, 1.00 against 1.00). Serie A and the Champions League remain somewhat high (1.05-1.09: there are fewer cards than ever and the level still lags a little) and the 2026-27 Premier League low (0.92; it's the only league where they go up, and the level shrinks it towards everyone's).
- **By probability band** (starters): in January, from 0.48 / 0.79 / 0.87 / 1.00 / 1.10 / 1.43 (under 5 %, 5-10 %, 10-15 %, 15-20 %, 20-30 % and over 30 %) to 0.66 / 0.99 / 0.95 / 1.01 / 1.02 / 1.39; in July, from 0.63 / 0.84 / 0.89 / 1.07 / 1.17 / 1.33 to 1.45 / 1.14 / 0.94 / 1.02 / 0.98 / 0.82. The extremes have few cases (the over-30 % band goes from 311 to 123 starters in January and from 221 to 50 in July).
- **With 1 − e^(−λ)** and the other changes, the log-loss is worse at both cut-offs (starters 0.4117 and 0.3999, against 0.4112 and 0.3992; all 0.2775 and 0.2712, against 0.2774 and 0.2709), and starters come out short (0.92 and 0.92).
- **"All" comes out high (1.05-1.08)** because the model assumes each substitute in the confirmed XI comes on 55 % of the time and plays 22 minutes, and from July to October they came on 45 % of the time and played 20. It affects every substitute market (pending in "Upcoming planned improvements"). Also, bets on a substitute who doesn't come on are voided, and the model gives their probability counting that they may not come on: for a substitute, "Yes" comes out low and "No" high.
- **With the model fixed for the 90 days** (no retraining, like the shots check above), starters stay at 0.966 → 0.998 (January, log-loss 0.4148 → 0.4104) and 1.030 → 1.043 (July, 0.4007 → 0.3977): each league's level isn't updated and in July the pre-summer one applies.

To reproduce: `medir_tarjetas.py FROM 90 output.json --semanal` (and `--registros` for each player) and `medir_k.py` for the shrinkage, in the notes of the 22-10-2026 session (not in the repository).

**Bet Builders with players** (`MatchModel.joint_prob`): if the team scores k goals, each one is scored by the player with their share of the team's expected goals (and assisted with their share of assists). That way "Real Madrid win and Mbappé scores" is computed on the scoreline matrix, with its positive correlation, and "Arsenal or draw and Kane scores or assists" with its negative correlation. Several player selections from the same team are combined by inclusion-exclusion. With a single player the probability is the same as the standalone market. Corners, cards, shots and fouls don't depend only on the scoreline: in a Bet Builder they're multiplied as if independent and the result is marked **approximate**.

## 5. Line-ups and absences (`features/lineup.py`)

`quality = ln(1 + market_value_M€) + 0.5 × (rating − 6.8)` (rating capped at ±1).
The XI's attacking and defensive strength = average weighted by position:

| | GK | DEF | MID | FWD |
|---|---|---|---|---|
| Attack | 0 | 0.25 | 0.7 | 1 |
| Defence | 1 | 1 | 0.6 | 0.15 |

It's compared with the **usual XI** (average of the last 8 confirmed starting line-ups):
`goals_for × exp(0.10 × Δattack)` and `goals_against × exp(−0.10 × Δdefence)`.
Without a published line-up, it starts from the usual XI and subtracts the regular starters who are out.
The 0.10 coefficient is calibrated with FotMob's historical confirmed XIs (2,119 matches from 2024-26). It used to be 0.30, a prior estimate that exaggerated the effect (see backtest).
Limitation: in old matches the market value is the one at download time, not the one at the time.

## 6. Value, confidence and bet of the day

- **Final probability** = 25 % model + 75 % sharp market (Pinnacle/Betfair without margin) when it exists. If it doesn't, the model only.
  Since 21-11-2026 the sharp market is also used in **team goals, both teams to score and the European handicap** (Pinnacle's own lines from OddsPapi) and in **double chance and draw no bet** (from its 1X2); before, only in 1X2, over/under goals and Asian handicap, and the rest went on the model alone. Real case: Parma - Roma, Roma under 2.5 goals at 1.91 on Betano, was the bet of the day with the model's 64 % and +22.7 % value, while Pinnacle had it at 48 % (2.00 / 1.84); blended, 52 % and no value. The `apuestas backtest` has no historical team-goal odds, so it measures with the ones implied by Pinnacle's 1X2 and over/under 2.5 (`market.implied_goals`): log-loss of under 0.5, 1.5 and 2.5 goals of each team and of both teams to score, 5,149 matches of the eight leagues in 2024-26: model 0.5442, Pinnacle 0.5437, 25/75 blend 0.5432 (blend − model −0.0010 ± 0.0008). With Pinnacle's real lines, in the 63 matches played with a saved preview since 12-11-2026 (309 lines): model 0.6199, Pinnacle 0.6144, blend 0.6136 (−0.0063 ± 0.0169, too few matches to tell apart). There's no betting backtest of these markets: there are no historical bet365 or Betano odds for them.
- **Expected value** = prob × odds − 1 (corrected by the probability of a refund on Asian lines).
- **Draw calibration: measured and not needed** (29-10-2026, `experimentos/validacion/empates.py`). The audit saw too few draws with the public data. With the database, the factor that multiplies the diagonal of the scoreline matrix, learned each month with the earlier ones, stays at 1.00-1.01 and improves nothing (1X2 log-loss +0.0001 ± 0.0002). By band, what the model gives and what happened: 0.176 and 0.173; 0.243 and 0.232; 0.278 and 0.291; 0.315 and 0.324 (Pinnacle, 0.166-0.310). The Dixon-Coles rho, fitted at each retraining, already captures it.
- **Comparing prices: Betano against no-vig Pinnacle** (since 29-10-2026, `services/compare.py`, Today's "Against Pinnacle" tab, `GET /compare`, MCP `comparar_casas`). It doesn't use the model. For each match that hasn't started yet, each Betano price is compared with Pinnacle's fair price for the same line (all sides, `analysis.book_fair_prob`), without the lines the bookmaker no longer offers (below). It shows up if it pays at least 2 % more. It's the version within the project's reach of the only thing that gave a positive return in the audit. Measured with the odds saved since 19-10-2026 (`experimentos/validacion/betano_pinnacle.py`, 67 finished matches; each selection counts once, the first download in which it passes; CLV against no-vig Pinnacle in its last snapshot before kick-off, when it's later):

  | Markets | Edge | Bets | Return | CLV |
  | --- | --- | --- | --- | --- |
  | Goals (1X2, handicaps, over/under, both teams to score) | ≥ 2 % | 23 | +17 % ± 49 % | +0.4 % (16 with closing) |
  | Corners and cards | ≥ 0 % | 288 | +5 % ± 13 % | +3.5 % (163, 80 % positive) |
  | Corners and cards | ≥ 2 % | 194 | +7 % ± 16 % | +5.2 % (111, 86 % positive) |
  | Corners and cards | ≥ 5 % | 91 | +32 % ± 24 % | +8.3 % (49, 96 % positive) |

  In goals Betano almost never pays more than Pinnacle. In corners and cards, yes and often, and Pinnacle doesn't move towards Betano afterwards. What isn't known yet is whether Pinnacle is as sharp in stats as in goals. The intervals are optimistic: the lines of the same match are correlated. Repeat it when there are about 200 matches.
- **Lines the bookmaker no longer offers** (since 29-10-2026, `OddsSnapshot.last_seen_at`). A new price is only saved when it changes, so a line's last saved price didn't say whether the bookmaker still offered it: a withdrawn line kept its last price until the match, and "Value", the bet of the day and the comparison tool could come from it. Now each download notes on each line's last row that it saw it again, and `analysis._latest_odds` leaves out those not seen in the 12 hours before their bookmaker's last download (the 12 hours keep the 08:30 one inside when the pre-match Pinnacle download, which brings fewer matches, arrives later). Earlier rows don't have that date and count as current, so the effect starts with the 08:30 download on 30-10. How many lines Betano withdraws wasn't known: the data will show.
- **Learned blend and probability of value: measured and not applied** (29-10-2026, `experimentos/validacion/apilado.py`, 19,241 candidate selections from the 2024-26 backtest with Pinnacle). The model's weight was learned each month with the previous months (minimum log-loss of the linear blend), per market: in 1X2 and Asian handicap it drops to 0 (average 0.08 and 0.11) and in goals 2.5 it ends at 0.27. No blend is distinguishable from the fixed one:

  | Market | Learned − fixed | Pinnacle alone − fixed | Model alone − fixed |
  | --- | --- | --- | --- |
  | 1X2 | −0.0002 ± 0.0004 | −0.0003 ± 0.0005 | +0.0029 ± 0.0014 |
  | Over/Under 2.5 | +0.0001 ± 0.0003 | +0.0002 ± 0.0003 | +0.0006 ± 0.0010 |
  | Asian handicap | −0.0001 ± 0.0006 | −0.0004 ± 0.0006 | +0.0049 ± 0.0019 |

  Log-loss per selection, negative = better, paired 95 % margin. With value ≥ 3 % against bet365, the learned one gives fewer bets, but no rule has the sample to say anything: 1X2, 30 with the fixed one (return −30 % ± 47 %, CLV +4.3 %) and 11 with the learned one (+9 % ± 90 %, CLV +6.0 %); handicap, 64 and 65 (CLV +1.5 % and −0.9 %). Choosing by the **probability of value** (P(p > 1/odds) with the deviation of bet365's closing odds against the blend in the previous months) doesn't help either: in handicap, with P ≥ 60 %, 133 bets with CLV −0.8 % (37 % beat the close), and with P ≥ 75 %, 34 with −38 % ± 28 %. Without each prediction's own variance (dynamic strength would provide it, section 1) this probability is just the value divided by a σ per market and ranks almost the same as the value. The fixed 25 % stays.
- **Confidence** (0-1) = line-up (confirmed 1 · predicted 0.85 · absences only 0.72; the last XI FotMob gives when it doesn't have a predicted one yet counts as predicted, and only the official one as confirmed) × sample × market type (main 1 / stats 0.75 / player 0.65) × model-market agreement × rotation risk × market coverage (below).
- **Teams the market hasn't seen** (`analysis.MARKET_COVERED`). Each team's matches with closing odds over the last year are counted (`RatingModel.market_matches`). If either team has fewer than 10:
  - confidence is multiplied by a factor that falls linearly to 0.6 with 0 matches;
  - in goals markets (1X2, double chance, draw no bet, both teams to score, handicaps and over/under goals), if there's no sharp market, the probability is blended with that of the price itself without margin (5 % assumed). The model's weight is the same 25 % of the blend with Pinnacle when the team has 0 matches, and rises to 100 % with 10.

  It affects teams from leagues that aren't downloaded and that we only see in European cups (Bodø/Glimt, Slavia, Shakhtar…). **It's a prudence rule, not a fitted parameter**: those matches have no odds on football-data, so the backtest can't measure it. In the leagues nothing changes, because all their teams have odds. Example, Napoli-Bodø/Glimt (UCL, 20-10-2026):

  | Price | Before | Now |
  |---|---|---|
  | Bodø @9.00 | probability 32 %, value +185 %, confidence 0.65 | probability 15 %, value +39 %, confidence 0.31 (can't be the bet of the day) |
  | Napoli @1.30 | probability 44 % | probability 66 % |
- **Bet of the day**: the highest `value × confidence` with odds between 1.50 and 2.60, prob ≥ 60 %, value ≥ 3 % and confidence ≥ 0.60. **If none qualifies, there's no bet of the day.**
  **60 % minimum** (5-11-2026, owner's decision; before, 42 %): it also applies to the "Value" lists on Today and on the match page. Probability and value are computed the same way: only which bets are shown changes. With 60 % and value ≥ 3 %, the odds have to be 1.72 or more. **It doesn't improve the result:** in the 2024-08 to 2026-10 backtest (`experimentos/validacion/corte_60.py`, odds from 1.50 to 2.60, value ≥ 3 %, without filtering by confidence), it hits more often, but collects less:
  **No quarter lines** (7-11-2026, owner's decision): Asian handicap and over/under goals lines of 0.25, 0.75, 1.25… can't be bet at their bookmakers and aren't shown (`analysis.can_bet`). No probability changes: Pinnacle's quarter-line price still serves as the reference price.
  **Reviewers' verdict** (7-11-2026; since 19-11-2026, the betting table of ADR 0010): it doesn't change anything above, and neither do the agents' weights. It's Claude's opinion shown below the bet of the day. A bet goes "against a team on a streak" if that team has 3 wins in a row or 4 of its last 5 matches, in all competitions, and the bet wins when that team doesn't win or doesn't win by much: 1X2, double chance, draw no bet and handicaps in favour of the opponent, and "Under" on that team's goals. Not measured yet (`experimentos/validacion/veredicto.py`).

  | Strategy | Probability | Bets | Average odds | Expected | Hit rate | ROI | CLV |
  |---|---|---:|---:|---:|---:|---:|---:|
  | Model only | Under 60 % | 2,583 | 2.02 | 53.5 % | 48.8 % | −1.8 % ± 3.7 | +1.1 % |
  | Model only | 60 % or more | 515 | 1.80 | 63.7 % | 55.4 % | −1.7 % ± 7.2 | +0.9 % |
  | Model + Pinnacle | Under 60 % | 136 | 2.04 | 52.9 % | 47.7 % | −3.1 % ± 16.5 | +1.2 % |
  | Model + Pinnacle | 60 % or more | 30 | 1.79 | 65.7 % | 53.3 % | −7.1 % ± 31.8 | +3.2 % |

  When selecting by value, the model hits less often than it promises, and among those of 60 % or more the difference is 8 to 12 points. With real money the same happened: of the 144 saved bets that cleared the threshold and already have a result, those of 60 % or more (52, average probability 67 %, odds 1.64) won 26 and lost 26, −9.7 units; those under 60 % (92, 52 %, odds 2.08), 48 and 43, +7.2 units. Too few to draw conclusions.
  It can only come from **goals markets** (1X2, double chance, draw no bet, both teams to score, handicaps and over/under goals), which are the ones validated in the backtest against real odds. Corners, cards, the other stats and player props are shown as value bets, but can't be the bet of the day until they're validated (`APUESTAS_PICK_ALLOW_STAT_MARKETS=true` changes that).
- **Disagreement with the bookmaker in stats.** In corners, cards and the other stats, if the bookmaker has every side of the line (over and under, or both teams of the handicap), its no-vig probability is computed and compared with the model's:
  - up to 5 points of difference, the confidence doesn't change;
  - from 5 to 20 points, it falls linearly to ×0.3 (`STAT_DISAGREE_*` in `analysis.py`).

  The model's probability isn't touched: only the confidence. It's a prudence rule, because there's no history of stat odds to fit it with the backtest.

  Reason: with Betano's odds (OddsPapi, 19-10-2026), the model saw "value" in 412 prices of the next day's 9 Champions League matches. Some were absurd, like "Napoli over 10.5 corners" at 9.00 with +164 %. The bet of the day came from a corners handicap with +41 %.
- **Teams with few matches with that stat** (`analysis.STAT_COVERED`, since 21-10-2026). In corners, cards and the other stats, if the less-seen of the two teams has fewer than 10 (weighted) matches with that stat, the probability is blended with the bookmaker's no-vig one (or with the single price, minus 5 %, if the bookmaker doesn't have both sides). The model's weight is n / 10: with 0 matches the bookmaker rules and no value can come out; with 10 or more, only the model. It's stricter than the goals rule (which leaves 25 % model with 0 matches) because the stat models have no backtest against odds at all. It affects the same European opponents (Viking, LASK, Slavia, Shakhtar, Bodø/Glimt…). It's a prudence rule, not a fitted parameter.

  Aston Villa-Viking (Viking with 1.9 matches): "Viking corners: over 5.5" at 6.50 goes from +73 % (with only the shrinkage) to +11 %, with confidence 0.08. Before, 34 corners prices from that match came out with value and the biggest gave +232 %; now the biggest is that one, with +11 %.
- **What counts in the counters is what was announced** (since 29-10-2026, `pick.announced_*` and `was_pick_of_day`). Each recalculation updates the saved bet, but the odds, probability and value of the first time it cleared the threshold stay fixed, and the hits, profit and CLV are measured with them. A bet of the day or one that cleared the threshold and was later withdrawn still counts and is settled. Before, the counter measured the last recalculation and withdrawn bets disappeared (the audit pointed it out). When moving to the fixed copy, the earlier ones were filled in with what was already counted, so the figures didn't change: bet of the day 5 of 7 (+2.58 u) and those that clear the threshold 22 of 43 (−3.17 u, CLV −3.28 %).
- **Stake**: Kelly × 0.25, capped at 3 % of the bankroll. Loss limits: 5 % daily and 10 % weekly.
- **CLV of the saved bets** (`picks.closing_reference`, since 2026-10-28). When settling, each saved bet (and each logged bet) is compared with the **fair** price (no margin, `betting/odds.py::devig`) of the sharpest reference available before the match: CLV = odds taken × fair probability − 1. Order: Pinnacle's or Betfair's closing odds (football-data), Pinnacle's last price before kick-off (OddsPapi) and bet365's closing odds. The reference has to have every side of that line (over and under, the three of the European handicap, the two of the Asian, yes and no); otherwise, the bet has no CLV and the dashboard says why. Which bookmaker it comes from and when that price was first seen are saved (`pick.closing_source`, `pick.closing_at`).

  Why football-data's closing odds aren't enough: they only bring the 1X2, over/under 2.5 and the main Asian handicap for the leagues, days after the match, and almost every bet that clears the threshold is from Betano in team goals, European handicap or both teams to score. Measured on 2026-10-28 with the 40 settled ones that clear the threshold: bet365's or Betfair's closing odds served for 2; the last saved Pinnacle price, for all 40, but only 24 less than 3 hours before kick-off (the 08:30 download is far from afternoon or next-day matches). That's why, **about 15 minutes before each kick-off time with open bets that clear the threshold**, the worker downloads Pinnacle through OddsPapi (`job_closing_odds`; at most `APUESTAS_ODDSPAPI_CLOSING_PER_DAY` = 3 downloads a day, about 40-90 more requests a month, approved by the user on 2026-10-28).

  First results (2026-10-28, without the pre-kick-off download): **average CLV −3.5 %** across the 40 that clear the threshold (9 of 40 positive): the Betano and bet365 prices the model picks are, on average, 3.5 % below Pinnacle's fair price. By age of the reference: at the close (Betfair) +2.8 % in 2; under 3 h −3.2 % in 22; 3 to 12 h −1.1 % in 4; over 12 h −6.1 % in 12. It matches the backtest (the model doesn't beat the market in goals). With a few hundred bets the CLV will say whether there's an edge much sooner than the ROI: with 40, the ROI has a margin of about ±15 points.

## 7. Backtest (`backtest/engine.py`)

> **Measurement scripts that weren't kept** (10-11-2026). The scripts cited in this section by bare name (`bt.py`, `cmp.py`, `wf.py`, `ana.py`, `frente_casas.py`, `medir_k.py`… and session-notes folders like `nivel-liga/`) lived on the owner's previous PC and were lost: they were never in the repository. The figures stay as a record of what was measured. To measure again, use `apuestas backtest` and the scripts in `experimentos/`, which are in the repository.

Walk-forward: each week it's refitted with earlier data and bets are placed against **bet365's opening odds**. CLV against bet365's closing odds.

**Seasons 2024-25 and 2025-26** (2,132 EPL, BUN and LAL matches; the log-loss is measured on the 1,998 with bet365 and Pinnacle odds). Already with complete FotMob details: line-ups, referees and xG for every match since 2023. The "previous model" was measured again with complete data (it used to give 0.992 with partial data).

| 1X2 log-loss | Model | bet365 | Pinnacle | 25/75 blend |
|---|---|---|---|---|
| Previous model (goals/xG only) | 0.993 | 0.975 | 0.975 | 0.977 |
| **With market ratings** | **0.981** | 0.975 | 0.975 | 0.976 |

Paired improvement per match: −0.0116 ± 0.0029 (about 4 standard errors). Brier: 0.591 → 0.584 (bet365 0.581). The distance to Pinnacle falls from 0.017 to 0.006.

Weight and half-life of the market observations (model log-loss):

| Weight \ half-life | 7 days | 14 days | 28 days | 60 days |
|---|---|---|---|---|
| 8 | 0.9877 | 0.9859 | 0.9850 | 0.9854 |
| 32 | 0.9836 | 0.9824 | 0.9827 | 0.9846 |
| 64 | 0.9819 | 0.9815 | 0.9824 | 0.9845 |
| 128 | 0.9809 | **0.9811** | 0.9822 | 0.9845 |

With more weight it barely changes (256 and 512 with 7 days: 0.9804 and 0.9803). The differences within the plateau are noise. 14 days was chosen because it holds up better at the start of the season (August-September: 0.956 against 0.958 with 7 days).

| Strategy (value ≥ 3 %) | Previous: bets | ROI | Average CLV | New: bets | ROI | Average CLV |
|---|---|---|---|---|---|---|
| Model only | 2,668 | −4.2 % | +0.2 % | 1,559 | −6.8 % | +0.5 % |
| · Asian handicap | 1,289 | +0.3 % | +0.2 % | 849 | −4.2 % | +0.2 % |
| · over/under 2.5 | 770 | −8.6 % | +0.2 % | 282 | −3.1 % | +2.1 % |
| · 1X2 | 609 | −8.2 % | +0.1 % | 428 | −14.4 % | −0.2 % |
| Model + market | 290 | −11.1 % | +1.1 % | 82 | −23.4 % | +2.2 % |
| bet365 against Pinnacle (no-vig) | 4 | — | — | 4 | — | — |

The ROI's standard error with 1,500-2,700 bets at odds ~2.2 is 2-3 points, so the drop in ROI isn't significant. The rise in CLV (and in the % of bets that beat the close, 42 % → 45 %) is small.

**Line-ups** (`apuestas backtest --lineups`; 1,986 matches with both teams' confirmed XI and odds). Poisson regression of real goals/xG on the model's mean and the difference between the XI and the usual XI (4,238 team-matches, errors clustered by match):

| Target | β attack | β defence |
|---|---|---|
| Goals | 0.11 ± 0.05 | 0.10 ± 0.06 |
| xG | 0.06 ± 0.03 | 0.08 ± 0.04 |

| 1X2 log-loss | No adjustment | β = 0.05 | **β = 0.10** | β = 0.15 | β = 0.30 (previous) | bet365 | Pinnacle opening | Pinnacle closing |
|---|---|---|---|---|---|---|---|---|
| | 0.9812 | 0.9803 | **0.9798** | 0.9797 | 0.9818 | 0.9759 | 0.9759 | 0.9630 |

With β = 0.10 the improvement over no adjustment is −0.0014 ± 0.0010; with 0.30 the model got worse. The improvement comes mainly from LaLiga (−0.003); in the Premier League it's nil. The backtest's bets don't use this adjustment: the XI comes out ~1 h before the match and the opening odds are from days before.

Variants tried without improvement (log-loss difference against no adjustment; 2,119 league matches + 361 Champions League):

| Variant (β = 0.10 unless stated) | Leagues | Champions League |
|---|---|---|
| Usual XI from all competitions (kept) | −0.0014 ± 0.0009 | −0.0011 ± 0.0024 |
| Usual XI from the same competition | −0.0012 ± 0.0009 | −0.0018 ± 0.0024 |
| League usual XI against European cups | −0.0012 ± 0.0009 | −0.0018 ± 0.0024 |
| Adjustment cap (±10 % on the goals mean) | −0.0015 ± 0.0009 | −0.0010 ± 0.0024 |
| β = 0.30 (previous) | +0.0013 ± 0.0028 | +0.0004 ± 0.0072 |

**Other XI quality indices** (14-11-2026, `experimentos/validacion/calidad_once.py`; 6,566 matches with both teams' confirmed XI, from August 2024 to 9-11-2026: 6,128 from the eight leagues and 438 from the Champions League). It was tested whether an index made from what each player did before the match captures more than the current one, which is almost only market value (the season rating only comes in 807 of 223,595 line-up rows). Each index measures today's XI against the usual XI (the starters of the last 8 XIs, weighted by how many times they started); their β are fitted on two seasons and measured on the third, so everything is out of sample except the current one with β = 0.10. 1X2 log-loss difference (negative = better):

| Index | Leagues, vs no adjustment | Leagues, vs current | Champions, vs no adjustment | Champions, vs current | All, vs current |
|---|---|---|---|---|---|
| Current, β = 0.10 (production) | −0.0012 ± 0.0009 | — | −0.0007 ± 0.0039 | — | — |
| Current, fitted β (0.15 and 0.13) | −0.0012 ± 0.0012 | 0.0000 ± 0.0004 | −0.0005 ± 0.0056 | +0.0002 ± 0.0018 | 0.0000 ± 0.0004 |
| FotMob rating over their last 10 matches | −0.0004 ± 0.0011 | +0.0008 ± 0.0012 | −0.0023 ± 0.0047 | −0.0016 ± 0.0049 | +0.0007 ± 0.0012 |
| xG + xA per 90 over their last 10 matches | −0.0002 ± 0.0006 | +0.0010 ± 0.0010 | −0.0006 ± 0.0026 | +0.0001 ± 0.0041 | +0.0009 ± 0.0010 |
| Usual starters (in how many of the last 8 XIs they started) | −0.0015 ± 0.0015 | −0.0003 ± 0.0015 | −0.0080 ± 0.0064 | −0.0073 ± 0.0060 | −0.0008 ± 0.0014 |
| **Current + usual starters** | −0.0022 ± 0.0018 | −0.0009 ± 0.0013 | −0.0070 ± 0.0081 | −0.0063 ± 0.0055 | **−0.0013 ± 0.0012** |
| All four together | −0.0020 ± 0.0019 | −0.0008 ± 0.0014 | −0.0067 ± 0.0087 | −0.0060 ± 0.0063 | −0.0011 ± 0.0014 |

Reading:

1. **Recent rating and xG + xA add nothing.** Players' recent form is already in the team's strength; what the XI adds is who plays, not how they had been playing. (The rating had already come out neutral in October with another replication.)
2. **Raising the current index's β changes nothing**: 0.10 is still fine.
3. **Counting how many usual starters play is the only thing that adds**, above all in the Champions League, where there's more rotation. Together with the current index it reaches just its margin with all matches (−0.0013 ± 0.0012) and in the Champions League (−0.0063 ± 0.0055), not in the leagues alone (−0.0009 ± 0.0013). By season, against no adjustment: 2024-25 −0.0035 ± 0.0025, 2025-26 −0.0005 ± 0.0028 and 2026-27 −0.0058 ± 0.0043. Six variants were tried in three groups, so one that grazes its margin may be luck: **it doesn't go into production**; it's measured again at the end of the 2026-27 season (about 2,500 more matches), and if it holds it's proposed to the owner.
4. **Size matters more than sign.** In the 3,951 league matches with odds: model without adjustment 0.9603, with the current index 0.9588, with the current one and usual starters 0.9584; bet365 days before 0.9571, Pinnacle days before 0.9565 and Pinnacle's closing odds 0.9537. With the XI already published, the model is still behind the price the bookmaker gave days earlier without knowing it. No line-up index closes that gap: what the closing odds know beyond it isn't in this data.

Limit of the measurement: the saved market value is the one on the download day (November 2026 for the whole history), so the current index sees the future in old matches. No bigger advantage is noticed in the old seasons (2024-25 −0.0021, 2025-26 −0.0001, 2026-27 −0.0021 in the leagues), but the comparison favours the current one, not the new ones.

*Predicted* XIs (FotMob) can't be calibrated because their history isn't saved: when the confirmed one comes out, the row is overwritten. The same β is applied to them, which is probably somewhat high for them, because a badly guessed predicted XI adds noise. Example: in Liverpool-Villarreal (UCL, 20-10-2026) Liverpool's predicted XI includes several substitutes and Villarreal's is the Champions League one (in the league it rotates). With β = 0.30 the model gave the home team 0.43; with 0.10 it gives 0.59; the market, ~0.66.

**Referee in cards** (log-likelihood improvement per match against the model without referee; 2,105 matches):

| K | Total | Premier League | Bundesliga | LaLiga |
|---|---|---|---|---|
| 20 | +0.0041 | −0.0105 | +0.0066 | +0.0170 |
| 40 | +0.0048 | −0.0066 | +0.0060 | +0.0155 |
| **80** | **+0.0044** | −0.0034 | +0.0046 | +0.0122 |
| 120 (previous) | +0.0037 | −0.0022 | +0.0036 | +0.0099 |
| 250 | +0.0024 | −0.0009 | +0.0021 | +0.0061 |

K = 80 improves on 120 by +0.0006 ± 0.0004. K = 40 gives slightly more on average, but with more variance. In the Premier League the referee's history doesn't predict cards with any K (−0.003 ± 0.002 with K = 80). No per-league exception has been set, so as not to fit it to the same sample. In fouls K = 20 stays (with 40 the difference is smaller than its error).

**European cups** (`--europa`; there are no football-data odds, so only the model is measured). The model's 1X2 log-loss: Champions League 0.903 (377 matches), Europa League 0.984 (371) and Conference 1.021 (282). Without a market reference, how far off it is can't be said. There are two known limitations:
- 102 teams only appear in European cups: they're from leagues the model doesn't use. They have no market ratings, so their rating comes only from a few European matches. Example: Bodø/Glimt comes out almost as strong as Napoli (+0.62 against +0.67), while Napoli's 1.30 odds imply ~77 %. A team-specific home advantage (Bodø: +0.3 xG at home and −1.7 away) was tried and doesn't improve: it makes the leagues worse by +0.001 and doesn't change the Champions League. The football-data extra leagues cover 43 of those 102 teams, but with the current model they don't help (below); the other 59 are from leagues football-data doesn't have (Czechia, Croatia, Serbia, Ukraine, Cyprus, Israel...).
- **football-data extra leagues** (19-10-2026): Austria, Denmark, Norway, Switzerland, Poland, Sweden, Romania, Finland and Ireland, with 6,852 matches with closing odds since 2023. With them, 43 of the 102 teams have market ratings: 35 from those leagues (Bodø/Glimt, Salzburg, Young Boys, Copenhagen, Legia, Malmö, FCSB...) and 8 that were duplicates. **They're downloaded, but not used for training** (`APUESTAS_EXTRA_LEAGUES_IN_MODEL=false`), because they don't improve the current model. A/B on the same database, with log-loss per match on the matches evaluated in both versions:

  | Model 1X2 log-loss | Without extra leagues | With extra leagues | Difference |
  |---|---|---|---|
  | Leagues (2,132 matches) | 0.9801 | 0.9800 | −0.0001 |
  | Champions League (377) | 0.9017 | 0.9064 | +0.0046 ± 0.0061 |
  | Europa League (371) | 0.9856 | 0.9842 | −0.0014 ± 0.0074 |
  | Conference (282) | 1.0150 | 1.0236 | +0.0085 ± 0.0108 |

  With the extra leagues, 5 Europa League and 8 Conference matches of teams that previously had no rating are also evaluated. So `APUESTAS_EXTRA_LEAGUES_IN_MODEL=true apuestas backtest --lineups --europa` gives 0.906 (377) / 0.984 (376) / 1.026 (290).

  The reason is that the model doesn't have a level per league. The L2 shrinks each team towards 0, so a whole league, connected to the others only by its European matches, moves as a block towards the average: Ireland comes out at the Eredivisie's level. The best teams in each league, who are far ahead of the rest, end up inflated. Bodø/Glimt goes from +0.62 to +0.93 (Napoli +0.73) and Napoli-Bodø goes from 47/25/28 to 39/24/37, with the market at ~77 % for Napoli. Also, those teams would stop triggering the prudence rule for teams the market hasn't seen (section 6). Lowering the L2 (0.5 or 0.1) separates the leagues more, but doesn't fix Bodø (+0.93 and +0.96).

  Experiment not applied: strength = league level + team deviation, with the L2 only on the deviation (league = that of its last league match). Without extra leagues: Champions League 0.8966, Europa League 0.9757, Conference 1.0122 and leagues 0.9798. With them: 0.8957 / 0.9719 / 1.0122 and leagues 0.9797. The improvement comes mainly from the level per league, and with it the extra leagues stop making things worse. But no difference is significant (cups together −0.008 ± 0.006 against the current model) and Napoli-Bodø is still far from the market (50/23/27).
- ~~There are duplicate teams across sources~~ **Fixed on 19-10-2026** (`ingest/dedupe.py`). 9 teams were merged:
  - AEK, PAOK, NEC Nijmegen, Royal Antwerp, Union Saint-Gilloise and Vitória de Guimarães: their European cups record wasn't connected to their league one.
  - Verona, Clermont and Saint-Étienne: each of their Serie A or Ligue 1 matches was **duplicated** (182 in total), one from FotMob and another from football-data. Each matchday's opponent "played twice".

  The cause was that, in the light leagues with FotMob, football-data created the match instead of looking it up. Also, Gladbach never had its football-data odds linked and was left without market ratings; now it has them.

  The ingest merges the safe pairs by itself: the same name after normalising, different sources, no matches between them and no different matches on the same day. The doubtful ones are listed with `apuestas equipos duplicados`, for example Aris (Greece) against Aris Limassol (Cyprus), which are different clubs.

  | Model 1X2 log-loss | Before | After merging |
  |---|---|---|
  | Leagues (2,132 matches) | 0.9811 | **0.9801** (bet365 0.9749) |
  | Champions League | 0.903 | 0.902 |
  | Europa League | 0.984 | 0.986 |
  | Conference | 1.021 | 1.015 |

  In the betting backtest, model only: 1,594 bets, ROI −6.3 % (before −6.8 %), a difference that is noise.
- The model is only trained with the competitions defined in `core/competitions.py`. The database is shared, and a branch can load new leagues that haven't been validated yet.

| Stats (log-likelihood of the total per match) | Improvement over the league average |
|---|---|
| Fouls | +0.160 (referee: +0.006 more) |
| Shots | +0.036 |
| Shots on target | +0.024 |
| Cards | +0.022 (referee: +0.004 more) |
| Corners | +0.008 |

**Stats shrinkage** (21-10-2026; `apuestas backtest --europa`, against `--count-l2 1` for the previous fixed L2). Log-likelihood per match, of the total and of the two teams separately (`<stat> por equipo`), on 2,132 league matches and 378 Champions League ones. In the Champions League, 108 matches have a team with fewer than 10 matches with stats ("little data"; `:pocos_datos` in the output). Difference against the fixed L2, with the paired standard error:

| Stat (K) | Leagues: total | Leagues: per team | Champions: total | Champions: per team | Little data: total | Little data: per team |
|---|---|---|---|---|---|---|
| Corners (5) | +0.0030 ± 0.0011 | +0.0008 ± 0.0040 | +0.019 ± 0.008 | −0.004 ± 0.023 | +0.043 ± 0.022 | +0.014 ± 0.056 |
| Cards (10) | +0.0082 ± 0.0019 | +0.0111 ± 0.0024 | +0.015 ± 0.012 | +0.025 ± 0.015 | +0.026 ± 0.038 | +0.056 ± 0.045 |
| Fouls (5) | +0.0028 ± 0.0018 | +0.0081 ± 0.0027 | +0.045 ± 0.018 | +0.044 ± 0.027 | +0.111 ± 0.059 | +0.137 ± 0.082 |
| Shots (1) | +0.0014 ± 0.0005 | −0.0022 ± 0.0023 | +0.014 ± 0.006 | +0.004 ± 0.023 | +0.038 ± 0.019 | +0.065 ± 0.052 |
| Shots on target (1) | +0.0013 ± 0.0004 | −0.0022 ± 0.0015 | +0.022 ± 0.008 | +0.019 ± 0.014 | +0.070 ± 0.028 | +0.114 ± 0.040 |

K was chosen with a grid (0.5 to 30) in that same walk-forward: the value that improves the total without making "per team" worse in the leagues. More shrinkage keeps improving the total, but makes the split between the two teams worse: in corners, with K = 20, "per team" drops −0.005 in leagues and −0.12 with little data. The order matches the one given by the real variation between teams (empirical: K ≈ 2-3 in shots, 8 in corners, 30-60 in cards), with more shrinkage where teams are more alike. In shots, "per team" in leagues drops a little with any K (−0.002, at 1-1.5 standard errors); it's accepted because of the improvement in the Champions League, which feeds the player props of those opponents. The 1X2 and the bets don't change (the goals model is the same). Before, the Champions League corners total predicted worse than the league average (−0.002); now, +0.017. (Later, shots and corners were shrunk towards the goals model's strength instead, with another K: see below.)

Check with the saved Pinnacle odds (47 matches from 19 to 21-10-2026 with corners and 38 with cards; model trained up to 19-10): average error of each team's corners mean against Pinnacle's (root mean squared error in logarithm) 0.158 → 0.128, and in teams with fewer than 10 matches, 0.281 → 0.167. In the total, 0.105 → 0.068. In cards, 0.212 → 0.162 per team and 0.170 → 0.128 in the total.

**Corners and shots across leagues: the goals model's strength as a guide** (21-10-2026; `apuestas backtest --europa`, against `--no-count-strength` for the previous model). With the shrinkage above a problem remained with well-known teams: against Pinnacle, the per-team error in corners was 0.178 in the Champions League and 0.095 in the leagues. Betis-Feyenoord gave Betis 4.2 corners and Feyenoord 5.6 (Pinnacle: 5.3 and 4.1). The cause is the one in section 3: the leagues only cross in these stats through the Champions League, and each league's level was set by the shrinkage.

Two fixes were tried in the same walk-forward: a **level per league** (strength = league level + team deviation, with the shrinkage only on the deviation and the league of its last league match, like the goals experiment), and the **goals model's strength as a guide** (section 3). In the output, `:entre_ligas` are the 260 Champions League matches between known teams from different leagues, and `:pocos_datos` the 108 with a team with fewer than 10 matches. Log-likelihood difference per match against the previous model, with the paired standard error:

| Corners: variant (K) | Leagues: total | Leagues: per team | Cross-league: total | Cross-league: per team | Little data: total | Little data: per team |
|---|---|---|---|---|---|---|
| Level per league (5) | +0.0007 ± 0.0004 | +0.0074 ± 0.0022 | −0.0025 ± 0.0036 | +0.007 ± 0.031 | −0.020 ± 0.013 | +0.064 ± 0.044 |
| Level per league and strength (5) | +0.0011 ± 0.0006 | +0.0124 ± 0.0036 | −0.0029 ± 0.0041 | +0.012 ± 0.031 | −0.018 ± 0.015 | +0.065 ± 0.051 |
| Strength (5) | +0.0014 ± 0.0006 | +0.0132 ± 0.0036 | −0.0016 ± 0.0031 | +0.041 ± 0.014 | +0.003 ± 0.006 | +0.060 ± 0.029 |
| Strength (10) | +0.0034 ± 0.0009 | +0.0205 ± 0.0037 | +0.0005 ± 0.0033 | +0.047 ± 0.014 | −0.001 ± 0.009 | +0.053 ± 0.029 |
| **Strength (20, applied)** | **+0.0045 ± 0.0016** | **+0.0275 ± 0.0043** | **+0.0019 ± 0.0050** | **+0.053 ± 0.015** | **−0.009 ± 0.014** | **+0.039 ± 0.033** |
| Strength (40) | +0.0034 ± 0.0026 | +0.0311 ± 0.0054 | +0.0015 ± 0.0075 | +0.056 ± 0.017 | −0.018 ± 0.018 | +0.023 ± 0.037 |

| Other stats: variant (K) | Leagues: total | Leagues: per team | Cross-league: total | Cross-league: per team | Little data: total | Little data: per team |
|---|---|---|---|---|---|---|
| **Shots: strength (8, applied)** | +0.0062 ± 0.0015 | +0.0230 ± 0.0033 | −0.0029 ± 0.0041 | +0.043 ± 0.014 | +0.034 ± 0.019 | +0.114 ± 0.045 |
| **On target: strength (8, applied)** | +0.0067 ± 0.0015 | +0.0161 ± 0.0023 | −0.0014 ± 0.0048 | +0.025 ± 0.011 | +0.089 ± 0.034 | +0.147 ± 0.044 |
| Cards: strength (10, not applied) | −0.0002 ± 0.0003 | +0.0024 ± 0.0011 | +0.0000 ± 0.0021 | −0.003 ± 0.004 | −0.002 ± 0.002 | +0.009 ± 0.007 |
| Fouls: strength (5, not applied) | +0.0010 ± 0.0005 | +0.0014 ± 0.0006 | −0.0048 ± 0.0031 | −0.008 ± 0.004 | +0.005 ± 0.005 | −0.001 ± 0.006 |

With strength as a guide, more shrinkage improves, the opposite of before: without strength, K = 10 in corners makes the split worse (−0.0008 ± 0.0019 per team in leagues and −0.054 ± 0.018 with little data). The K chosen was the one that improves the leagues and cross-league matches without noticeably worsening the little-data ones; those are also blended with the bookmaker (section 6). Across the whole Champions League (378 matches), corners per team +0.047 ± 0.014, shots +0.061 ± 0.016 and on target +0.059 ± 0.015; the total gets worse in none of them. Using goals attack and defence separately (four coefficients instead of two) gives the same as their sum. The 1X2, the backtest bets, cards and fouls don't change.

Check with the saved odds (model trained up to 20-10-2026; each team's mean comes from all the bookmaker's corners over/under and handicap lines, without margin). Error of each team's corners mean (root mean squared error in logarithm):

| Corners, error per team | Leagues | Champions, known teams | Champions, little data | All | Match total |
|---|---|---|---|---|---|
| Pinnacle (41 matches: 25 / 9 / 7), previous model | 0.095 | 0.178 | 0.170 | 0.132 | 0.068 |
| Pinnacle, level per league (5) | 0.090 | 0.160 | 0.150 | 0.120 | 0.069 |
| Pinnacle, level per league (10) | 0.087 | 0.151 | 0.139 | 0.114 | 0.059 |
| **Pinnacle, strength (20)** | **0.072** | **0.120** | **0.083** | **0.086** | **0.049** |
| Betano (47 matches: 29 / 11 / 7), previous model | 0.083 | 0.180 | 0.147 | 0.123 | 0.062 |
| **Betano, strength (20)** | **0.058** | **0.131** | **0.066** | **0.082** | **0.046** |

| Corners (home-away) | Pinnacle | Previous model | Level per league | Strength |
|---|---|---|---|---|
| Betis-Feyenoord | 5.3-4.1 | 4.2-5.6 | 4.6-5.2 | 4.8-4.9 |
| Porto-PSV | 5.6-4.2 | 5.0-4.6 | 4.3-5.2 | 5.2-4.2 |
| Club Brugge-Lens | 5.5-4.6 | 5.5-4.8 | 4.5-5.8 | 5.4-4.6 |
| Real Madrid-Leipzig | 7.0-3.5 | 7.2-4.3 | 7.2-4.2 | 7.0-3.9 |
| Manchester City-AEK | 7.8-2.2 | 5.5-3.5 | 7.9-2.4 | 6.4-3.1 |
| Napoli-Bodø/Glimt | 6.2-3.7 | 8.2-3.0 | 8.8-2.7 | 6.7-3.5 |

**Why not the level per league.** With so few cross-league matches, each league's level comes out very noisy: the Eredivisie, with 14 weighted matches, ends up almost at the level of the Spanish Segunda, and the Belgian league comes out so low that Club Brugge would have fewer corners than Lens at home. It improves the split within leagues, but barely in the Champions League (+0.007 ± 0.031 cross-league) and spoils cases that were fine (Porto-PSV, Club Brugge-Lens). With strength as a guide, each league's level comes from the goals model, which has much more data to compare leagues (closing odds and every match of the three European cups). Combining the two is worse than strength alone. (It was tried again with the Europa League and Conference stats, with almost twice as many crossings, and it doesn't improve either: see "Level per league with the Europa League and Conference crossings" below.)

**What remains.** With big teams there are still differences with Pinnacle: Betis-Feyenoord (4.8-4.9 against 5.3-4.1) and Bayern-Arsenal (4.6-4.2 against 5.5-4.2). In the 21-10 analysis, "Feyenoord corners: over 7.5" at 9.00 goes from +108 % to +41 %, but its confidence rises from 0.36 to 0.73, because the model and the bookmaker disagree less (section 6). Corners can't be the bet of the day (only goals markets). (Explained and partly fixed on 22-10-2026: see "Corners of the big home team in the Champions League" below.)

**Europa League and Conference stats** (21-10-2026). FotMob brings the same stats for these cups as for the Champions League. The 1,020 matches played since 2023-24 were downloaded into a copy of the database and measured with the same walk-forward, on the same matches, removing their stats only from the training data. Log-likelihood difference per match (positive = better), with the paired standard error:

| With UEL/UECL stats | Leagues: total | Leagues: per team | Champions: per team | Cross-league: total | Cross-league: per team | Little data: per team |
|---|---|---|---|---|---|---|
| Corners | +0.0000 ± 0.0004 | +0.0012 ± 0.0008 | +0.0015 ± 0.0036 | +0.0025 ± 0.0012 | +0.0043 ± 0.0023 | −0.005 ± 0.012 |
| Shots | +0.0001 ± 0.0006 | +0.0051 ± 0.0013 | +0.0079 ± 0.0075 | +0.0011 ± 0.0022 | +0.0129 ± 0.0046 | −0.003 ± 0.024 |
| On target | +0.0008 ± 0.0007 | +0.0029 ± 0.0010 | +0.0040 ± 0.0091 | −0.0013 ± 0.0026 | +0.0024 ± 0.0039 | +0.008 ± 0.031 |
| Fouls | −0.0011 ± 0.0010 | +0.0004 ± 0.0012 | +0.0202 ± 0.0066 | +0.0010 ± 0.0031 | +0.0076 ± 0.0052 | +0.052 ± 0.019 |
| Cards | +0.0012 ± 0.0009 | +0.0012 ± 0.0009 | +0.0023 ± 0.0036 | +0.0005 ± 0.0022 | +0.0021 ± 0.0025 | +0.002 ± 0.011 |

(The Champions League groups are defined with the model without the cups: 260 cross-league matches and 108 with little data.) The improvement is small but goes in the same direction in almost everything: above all shots and fouls, and cross-league corners. In the two cups' own matches, which couldn't even be measured before, the improvement is large (shots per team +0.082 ± 0.024 in the Europa League and +0.130 ± 0.057 in the Conference; fouls +0.10 in both), but those matches aren't analysed in the dashboard.

- **The cups' xG, out of the goals model.** If their xG goes in with the normal weight (85 %), the model's 1X2 log-loss gets worse in the Champions League (+0.0062 ± 0.0025 per match; 0.9018 → 0.9079 in `apuestas backtest --europa`) and in the Europa League (+0.0071 ± 0.0070), improves in the Conference (−0.027 ± 0.014) and doesn't change in the leagues (+0.0001 ± 0.0001). Since the matches analysed are league and Champions League ones, their matches go into the goals model with the result only, as before. With that, the 1X2, the log-loss per competition and the backtest bets don't change (0.9801; Champions League 0.9018 → 0.9017 because of the new results).
- **K and strength.** With this data, the goals model's strength is still needed: without it, corners per team −0.024 ± 0.004 in the leagues and −0.036 ± 0.013 cross-league against the current model. Doubling K improves the leagues (corners per team +0.0045 ± 0.0018) but makes teams with little data worse (−0.019 ± 0.010), the same as without the cups; K stays as it was.
- **Against the bookmakers** (the same 41 matches with Pinnacle odds and 47 with Betano as above, model up to 20-10): almost the same. Per-team error in corners with Pinnacle: leagues 0.072 → 0.072, Champions League with known teams 0.120 → 0.119, little data 0.083 → 0.081; with Betano 0.058 → 0.060, 0.130 → 0.128 and 0.066 → 0.066. Betis-Feyenoord goes from 4.8-4.9 to 4.6-4.7 (Pinnacle 5.3-4.1): the lack of Europa League data didn't explain those differences.

To reproduce: `apuestas backtest --europa` with and without the stats in the database (outputs in `var/backtests/uel_stats_{antes,final}_2024_2026.json`; `uel_stats_despues` is the variant with the cups' xG).

**Level per league with the Europa League and Conference crossings** (21-10-2026; tried and **not applied**). With the two cups' stats, the leagues cross in corners and shots almost twice as much as before. Cross-league matches weighted by age on 20-10-2026: Portugal 29, Eredivisie 26, Belgium 18, Turkey 18, Greece 16 and Scotland 10; the big five, from 42 to 58. The level-per-league test was repeated in the same 2024-26 walk-forward, with all stats in training. As before: strength = league level + team deviation, shrinkage only on the deviation, and each team's league is that of its last league match. Variants:

- **Level per league** without goals strength, with the earlier K (5 in corners, 1 in shots) or with the strength one (20 and 8).
- **Level and strength**: level per league plus the goals strength as a guide. G is the shrinkage of each league's level towards 0, in equivalent matches: with G = 0.1 the level is almost free; with G = 30 it only moves away from 0 if the crossings demand it.
- **Pace and strength**: only each league's pace (more or fewer corners for both teams, without touching how much one league dominates another), plus strength.
- **Level only for teams without a league**: teams from leagues that aren't downloaded (Bodø/Glimt, Slavia...) share a level; the rest, as now.

Log-likelihood difference per match against that day's model (goals strength as a guide, before the split by the 1X2 of 22-10; positive = better), with the paired standard error. With the cups' stats, in the Champions League there are 260 cross-league matches and 96 with little data. The last column is the 199 Europa League and Conference matches between known teams from different leagues (not analysed in the dashboard):

| Corners: variant | Leagues: total | Leagues: per team | Cross-league: total | Cross-league: per team | Little data: total | Little data: per team | UEL/UECL cross-league: per team |
|---|---|---|---|---|---|---|---|
| Level per league (earlier K) | −0.0032 ± 0.0016 | −0.0201 ± 0.0033 | −0.0010 ± 0.0053 | −0.008 ± 0.019 | −0.012 ± 0.013 | +0.023 ± 0.027 | −0.003 ± 0.021 |
| Level per league (strength K) | −0.0029 ± 0.0010 | −0.0253 ± 0.0052 | −0.0008 ± 0.0053 | −0.013 ± 0.019 | −0.020 ± 0.008 | +0.028 ± 0.029 | +0.007 ± 0.022 |
| Level and strength (G 0.1) | −0.0007 ± 0.0006 | −0.0018 ± 0.0008 | +0.0007 ± 0.0022 | +0.004 ± 0.016 | −0.017 ± 0.009 | +0.040 ± 0.027 | +0.013 ± 0.017 |
| Level and strength (G 30) | −0.0005 ± 0.0005 | −0.0009 ± 0.0006 | +0.0007 ± 0.0014 | +0.006 ± 0.008 | −0.005 ± 0.003 | +0.019 ± 0.009 | +0.016 ± 0.008 |
| Pace and strength | −0.0008 ± 0.0006 | −0.0010 ± 0.0006 | −0.0001 ± 0.0009 | +0.000 ± 0.001 | −0.014 ± 0.008 | −0.012 ± 0.008 | −0.001 ± 0.001 |
| Level only for teams without a league | −0.0000 ± 0.0001 | −0.0002 ± 0.0002 | −0.0003 ± 0.0003 | −0.000 ± 0.001 | −0.012 ± 0.007 | +0.016 ± 0.018 | −0.001 ± 0.001 |

| Shots and on target: variant | Leagues: total | Leagues: per team | Cross-league: total | Cross-league: per team | Little data: total | Little data: per team | UEL/UECL cross-league: per team |
|---|---|---|---|---|---|---|---|
| Shots: level per league (strength K) | −0.0020 ± 0.0010 | −0.0185 ± 0.0047 | +0.0061 ± 0.0038 | +0.011 ± 0.021 | +0.010 ± 0.010 | +0.097 ± 0.036 | +0.055 ± 0.031 |
| Shots: level and strength (G 0.1) | −0.0011 ± 0.0006 | −0.0008 ± 0.0012 | −0.0009 ± 0.0024 | +0.011 ± 0.019 | +0.008 ± 0.009 | +0.089 ± 0.031 | +0.040 ± 0.028 |
| Shots: level and strength (G 30) | −0.0009 ± 0.0004 | −0.0003 ± 0.0007 | −0.0005 ± 0.0012 | +0.010 ± 0.009 | +0.005 ± 0.003 | +0.039 ± 0.010 | +0.029 ± 0.011 |
| Shots: level only for teams without a league | +0.0002 ± 0.0001 | +0.0001 ± 0.0003 | +0.0000 ± 0.0002 | −0.000 ± 0.001 | +0.002 ± 0.006 | +0.034 ± 0.017 | −0.002 ± 0.001 |
| On target: level per league (strength K) | −0.0003 ± 0.0011 | −0.0088 ± 0.0037 | +0.0055 ± 0.0037 | +0.007 ± 0.013 | +0.008 ± 0.012 | +0.029 ± 0.031 | +0.015 ± 0.025 |
| On target: level and strength (G 30) | −0.0005 ± 0.0005 | +0.0004 ± 0.0006 | −0.0007 ± 0.0011 | +0.004 ± 0.004 | +0.005 ± 0.003 | +0.018 ± 0.008 | +0.009 ± 0.008 |

Check with the saved odds (the same matches as above; model trained up to 20-10-2026). Error of each team's corners mean:

| Corners, error per team | Pinnacle: leagues | Champions, known | Champions, little data | All | Betano: leagues | Champions, known | Champions, little data | All |
|---|---|---|---|---|---|---|---|---|
| **Current model (strength)** | 0.073 | **0.119** | **0.081** | **0.086** | 0.060 | **0.128** | **0.066** | **0.082** |
| Level per league (earlier K) | 0.089 | 0.141 | 0.177 | 0.120 | 0.077 | 0.160 | 0.172 | 0.119 |
| Level and strength (G 0.1) | 0.071 | 0.122 | 0.132 | 0.097 | 0.058 | 0.142 | 0.137 | 0.098 |
| Level and strength (G 30) | 0.072 | 0.120 | 0.084 | 0.087 | 0.059 | 0.133 | 0.080 | 0.085 |
| Pace and strength | 0.071 | 0.119 | 0.088 | 0.087 | 0.059 | 0.129 | 0.074 | 0.083 |

| Corners (home-away) | Pinnacle | Current model | Level per league | Level and strength (G 30) |
|---|---|---|---|---|
| Betis-Feyenoord | 5.3-4.1 | 4.6-4.7 | 4.4-4.9 | 4.6-4.8 |
| Bayern-Arsenal | 5.5-4.2 | 4.8-4.1 | 4.6-4.2 | 4.7-4.2 |
| Porto-PSV | 5.6-4.2 | 5.2-4.2 | 4.5-5.0 | 4.8-4.5 |
| Club Brugge-Lens | 5.5-4.6 | 5.4-4.6 | 4.9-5.3 | 5.2-4.8 |
| Manchester City-AEK | 7.8-2.2 | 6.5-3.1 | 7.3-2.7 | 6.8-2.9 |
| Napoli-Bodø/Glimt | 6.2-3.7 | 6.8-3.4 | 9.1-2.5 | 7.2-3.2 |

**Why it still doesn't work.** Now each league's level is distinguishable when it goes alone. Resampling the matches (bootstrap on 20-10-2026), a league's corners advantage over the others (attack level + defence level, relative to the Premier League) is −0.29 ± 0.10 in LaLiga, −0.58 ± 0.10 in the Eredivisie, −0.84 ± 0.11 in Portugal and −0.98 ± 0.12 in Scotland. But almost all of that is already explained by the goals model's strength. What's left per league on top of strength ranges from +0.04 to −0.44, with errors of ±0.04 to ±0.15, and doesn't predict better:
- **Corners**: no variant improves cross-league (the best, +0.006 ± 0.008 per team) and all make the leagues slightly worse. The level per league without strength falls well below (−0.020 ± 0.003 per team in the leagues). It also spoils Porto-PSV and Club Brugge-Lens, the same as without the cups.
- **Shots and on target**: with level and strength, the split between the two Champions League teams improves when one has little data (shots +0.039 ± 0.010 with G = 30) and in the cups. But the total doesn't improve in any group, in the leagues it gets slightly worse (−0.0009 ± 0.0004) and G was chosen looking at these same matches. Part of that improvement comes just from the shared level of teams without a league (+0.034 ± 0.017). There are no saved shots odds to check it against the bookmakers.
- **Against Pinnacle and Betano**, no variant improves in the Champions League, and Betis-Feyenoord and Bayern-Arsenal barely change. What's missing in those two matches isn't the shrinkage either: with K = 40 in corners they come out 4.8-4.6 and 4.8-4.2. Nor is it a home bias: in the 16 Champions League matches, the model's home mean is only 2.5 % ± 2.4 % below Pinnacle's. The cause turned out to be something else and was fixed on 22-10-2026: see "Corners of the big home team in the Champions League against Pinnacle" below.

The goals strength as a guide stays, without a level per league. The version of `ratings.fit` with a level per league for the counts wasn't kept in the code.

**Serie A and Ligue 1 as full leagues** (21-10-2026, at the user's request). Until then they were light leagues: they went into the model with the result, football-data's counts and the closing odds, but without xG (football-data doesn't bring it until 2026-27), without referee, without line-ups and without players. Now they have the same as the Premier League, the Bundesliga and LaLiga: FotMob and Understat xG, Opta stats, referee, line-ups and players. The 2,191 matches played since 2023-24 were downloaded into a copy of the database and the usual walk-forward (2024-25 and 2025-26) was repeated on the before and after copies, on the same matches. `apuestas backtest` now evaluates the five leagues by default and gives the log-loss of each one; `--ligas EPL,BUN,LAL` repeats the earlier figures.

Model 1X2 log-loss by competition, on all matches with a rating (paired difference after − before; negative = better). The "before" for the Premier League, the Bundesliga, LaLiga and the cups is the earlier backtest, with three leagues; for Serie A and Ligue 1, the before copy also evaluating those two leagues:

| Competition | Matches | Before | After | Difference |
|---|---|---|---|---|
| Premier League | 760 | 0.9935 | 0.9938 | +0.0003 ± 0.0002 |
| Bundesliga | 612 | 0.9801 | 0.9800 | −0.0001 ± 0.0002 |
| LaLiga | 760 | 0.9648 | 0.9647 | −0.0001 ± 0.0002 |
| Serie A | 755 | 0.9695 | 0.9695 | −0.0001 ± 0.0009 |
| Ligue 1 | 608 | 0.9664 | 0.9670 | +0.0007 ± 0.0011 |
| Champions League | 377 | 0.9017 | 0.9022 | +0.0005 ± 0.0005 |
| Europa League | 371 | 0.9858 | 0.9855 | −0.0003 ± 0.0004 |
| Conference | 282 | 1.0149 | 1.0151 | +0.0003 ± 0.0004 |

For the Premier League, +0.0002 comes just from estimating ρ (Dixon-Coles) with five leagues instead of three. No difference reaches two standard errors.

Against the bookmakers (matches with bet365 and Pinnacle odds):

| 1X2 log-loss | Model before | Model after | bet365 | Pinnacle | 25/75 blend |
|---|---|---|---|---|---|
| Premier League | 0.9975 | 0.9978 | 0.9995 | 0.9974 | 0.9966 |
| Bundesliga | 0.9749 | 0.9748 | 0.9652 | 0.9669 | 0.9681 |
| LaLiga | 0.9668 | 0.9667 | 0.9578 | 0.9585 | 0.9595 |
| Serie A | 0.9657 | 0.9656 | 0.9623 | 0.9602 | 0.9608 |
| Ligue 1 | 0.9644 | 0.9651 | 0.9646 | 0.9649 | 0.9639 |
| The five (3,495) | 0.9743 | 0.9744 | 0.9704 | 0.9700 | 0.9702 |

Backtest bets (model only, value ≥ 3 %): Serie A, from 565 bets with ROI −3.4 % to 562 with +2.7 % (CLV +0.3 % → +0.5 %); Ligue 1, from 437 with −4.2 % to 422 with −7.4 % (CLV +1.3 % in both). The five leagues together: 2,584 bets, ROI −4.1 %, CLV +0.6 %. With about 500 bets at odds ~2, the ROI's standard error is 4-5 points: none of these differences is significant.

xG barely moves the 1X2 because the model already followed those two leagues' closing odds (market ratings, section 1), which weigh the most. In Ligue 1 the model is level with the bookmakers (0.9651 against bet365's 0.9646), but, as in the other leagues, that doesn't produce profitable bets.

Stats (log-likelihood improvement per match against the league average; "per team" = the two teams separately; the referee, against the same model without referee):

| After | Premier League | Bundesliga | LaLiga | Serie A | Ligue 1 |
|---|---|---|---|---|---|
| Corners per team | +0.191 | +0.109 | +0.123 | +0.126 | +0.130 |
| Shots per team | +0.347 | +0.257 | +0.352 | +0.283 | +0.317 |
| On target per team | +0.150 | +0.236 | +0.234 | +0.191 | +0.255 |
| Fouls per team | +0.200 | +0.273 | +0.248 | +0.266 | +0.098 |
| Cards per team | +0.048 | +0.046 | +0.023 | +0.078 | +0.038 |
| Referee in cards | −0.004 ± 0.002 | +0.004 ± 0.003 | +0.011 ± 0.004 | +0.013 ± 0.002 | +0.003 ± 0.002 |
| Referee in fouls | +0.007 ± 0.005 | −0.005 ± 0.006 | +0.014 ± 0.006 | +0.006 ± 0.005 | +0.024 ± 0.008 |

The Serie A and Ligue 1 models beat the league average as much as those of the other leagues, and already did so before with football-data's counts (FotMob and football-data almost always give the same figures; they differ in 13-14 % of the rows, as in LaLiga). What's new is the referee, which football-data doesn't bring outside England: it clearly helps with Serie A cards and Ligue 1 fouls. In the usual leagues the stats don't change (±0.0002), and in the Champions League shots improve a little (per team +0.0026 ± 0.0008; cross-league +0.0032 ± 0.0011), with nothing getting worse beyond noise.

Players, out of sample (model trained up to the cut-off day; matches with a confirmed XI over the following 90 days; expected / real and log-loss against the average rate):

| Cut-off | League | Player-matches | Goal | Assist | Goal or assist | Goal log-loss |
|---|---|---|---|---|---|---|
| 15-01-2026 | Serie A | 5,612 | 275 / 292 | 195 / 192 | 448 / 461 | 0.168 (average 0.205) |
| | Ligue 1 | 4,184 | 265 / 251 | 193 / 193 | 433 / 417 | 0.183 (average 0.227) |
| | The six competitions | 27,220 | 1,623 / 1,633 | 1,175 / 1,171 | 2,645 / 2,654 | 0.185 (average 0.227) |
| 23-07-2026 | Serie A | 3,360 | 178 / 184 | 127 / 141 | 289 / 310 | 0.182 (average 0.212) |
| | Ligue 1 | 1,957 | 132 / 122 | 99 / 93 | 218 / 200 | 0.197 (average 0.233) |

Player goals and assists come out as well calibrated as in the other leagues. **Player shots, on the other hand, come out short in every league** (15-01-2026: 13,868 expected against 16,401 real; Serie A −12 %, Ligue 1 −10 %, Premier League −22 %). It doesn't come from the new leagues: each player's per-90' rates are fine (with the real minutes, 0.99 of the real figure), but the step from team to player divides the team's expected shots by its average against an "average opponent" from the whole database, with second divisions and light leagues, and that factor is 0.82 on average. It's the same problem player goals had until 20-10 (section 4). Fixed on 22-10-2026 with the share of the team's shots (section 4).

Line-ups: with the five leagues, the regression gives β attack 0.13 ± 0.04 and β defence 0.10 ± 0.05 in goals (7,694 team-matches), consistent with the 0.10 in use. In Serie A the XI adjustment doesn't change the log-loss (+0.0001) and in Ligue 1 it improves it slightly (−0.0006), as in the Premier League.

To reproduce: `apuestas backtest --lineups --europa` with the earlier code and the current one (`--ligas EPL,BUN,LAL`) on the before and after databases (per-match outputs in `var/backtests/ligue1_serie_a_{antes3,antes5,despues5}_2024_2026.json`).

**Portugal and Belgium as full leagues** (29-10-2026, at the owner's request). Like Serie A and Ligue 1 a week earlier: they were light leagues that went into the model with the result, football-data's counts and the closing odds, but without xG, referee, line-ups or players. Now they have FotMob's details (xG, Opta stats, referee, XI and players) for the 2,018 matches played since 2023-24; Understat doesn't cover these two leagues. Unlike Serie A and Ligue 1, FotMob didn't download them even as light leagues: the 2,014 existing matches had been created by football-data, and FotMob reuses them instead of duplicating them (`store.upsert_fotmob_match`; nine teams needed a variant in `names._TEAM_SEEDS`, like "OH Leuven" against "Oud-Heverlee Leuven"). Belgium plays a regular season and playoffs (with points halved, which doesn't affect the goals model): FotMob and football-data bring both, and FotMob adds the final of the European playoff each season. In 2026-27 FotMob has it with 18 teams and 34 matchdays. The usual walk-forward (2024-25 and 2025-26) on the before and after database copies, with `main`'s code of 29-10-2026 (home advantage per competition included). `apuestas backtest` now evaluates the seven leagues by default; `--ligas EPL,BUN,LAL,SA,L1` repeats the earlier figures.

Model 1X2 log-loss, on the same matches (paired difference after − before; negative = better):

| Competition | Matches | Before | After | Difference |
|---|---|---|---|---|
| Portugal | 608 | 0.9185 | 0.9191 | +0.0006 ± 0.0010 |
| Belgium | 613 | 1.0038 | 1.0029 | −0.0009 ± 0.0009 |
| The five earlier ones | 3,495 | 0.9745 | 0.9745 | 0.0000 ± 0.0000 |
| Cups (UCL, UEL, UECL) | 1,030 | 0.9621 | 0.9621 | 0.0000 ± 0.0002 |

That "before" already evaluates the seven leagues. What also changes in production is that ρ (Dixon-Coles) is estimated with seven leagues instead of five: against the five-league backtest, the five earlier ones +0.0001 ± 0.0001 (Premier League +0.0003 ± 0.0002, Ligue 1 −0.0003 ± 0.0003) and the Champions League −0.0010 ± 0.0003 (cups −0.0007 ± 0.0002). FotMob's xG barely moves the two leagues' 1X2 because the model already followed their closing odds (section 1).

Against the bookmakers (matches with bet365 and Pinnacle odds; paired difference of the model against bet365):

| 1X2 log-loss | Model before | Model after | bet365 | Pinnacle | 25/75 blend | Model − bet365 |
|---|---|---|---|---|---|---|
| Portugal (588) | 0.9135 | 0.9145 | 0.9173 | 0.9176 | 0.9157 | −0.0028 ± 0.0036 |
| Belgium (587) | 1.0049 | 1.0041 | 1.0065 | 1.0100 | 1.0062 | −0.0024 ± 0.0034 |
| The seven (4,563) | 0.9700 | 0.9700 | 0.9682 | 0.9684 | 0.9677 | +0.0018 ± 0.0014 |

In the two new leagues the model is **level** with bet365: slightly ahead, but by less than one standard error, the same as before the change. In Belgium, Pinnacle (up to 2025-26) predicts worse than bet365. Backtest bets (model only, value ≥ 3 %): Portugal, from 347 bets with ROI +6.1 % to 352 with +4.2 % (CLV +1.7 % → +1.4 %); Belgium, from 307 with −0.1 % to 264 with +1.4 % (CLV +1.3 % → +1.5 %). With about 300 bets at odds ~2 the ROI's standard error is about 6 points: **it's not a proven edge**. The seven leagues together: 2,966 bets, ROI −4.0 %, CLV +0.9 %.

Stats (log-likelihood improvement per match against the league average, after; the referee, against the same model without referee):

| After | Portugal | Belgium |
|---|---|---|
| Corners per team | +0.286 | +0.070 |
| Shots per team | +0.482 | +0.271 |
| On target per team | +0.323 | +0.187 |
| Fouls per team | +0.419 | +0.122 |
| Cards per team | +0.066 | +0.048 |
| Referee in cards | +0.013 ± 0.004 | +0.007 ± 0.003 |
| Referee in fouls | +0.007 ± 0.006 | +0.004 ± 0.007 |

They beat the league average like the other leagues (before, with football-data's counts, almost the same: shots per team +0.482 and +0.270, corners +0.285 and +0.068). What's new is the referee, which helps with both leagues' cards. The paired comparison of these two leagues' stats isn't valid, because what's observed changes: FotMob's figures now rule (as in the other leagues), and in Portugal they differ from football-data's in 31 % of the shots rows (FotMob +0.4 per team), 19 % of on target and 12 % of fouls; in Belgium, in 13 % of shots; in Serie A, in 4.5 %. In the five usual leagues the stats don't change (per team, ±0.0004 at most).

Players, out of sample (model trained up to the cut-off; matches with a confirmed XI over the following 90 days; expected / real and log-loss against the average rate):

| Cut-off | League | Player-matches | Goal | Assist | Shots | Goal log-loss |
|---|---|---|---|---|---|---|
| 15-01-2026 | Portugal | 4,231 | 234 / 255 | 166 / 177 | 2,466 / 2,546 | 0.1882 (average 0.2277) |
| | Belgium | 3,911 | 237 / 242 | 182 / 165 | 2,421 / 2,516 | 0.2005 (average 0.2321) |
| 23-07-2026 | Portugal | 2,583 | 141 / 137 | 97 / 99 | 1,386 / 1,383 | 0.1681 (average 0.2074) |
| | Belgium | 2,320 | 144 / 159 | 108 / 114 | 1,431 / 1,604 | 0.2120 (average 0.2498) |

Calibrated as in the other leagues (across the seven, goals 2,040 / 2,130 and 1,256 / 1,318), and better than the average rate in every market. Belgium's shots in July (0.89) come up short like the other leagues' in 2026-27 (section 3, each league's recent level; this cut-off leaves the model fixed for 91 days).

OddsPapi spend, with the real calendar from August 2025 to November 2026: the API allows 5 competitions per request and with eight, almost every day more than 5 play in the next 3 days, so the daily Betano and Pinnacle download goes from 38-68 to 70-106 requests a month; with the catalogues and CLV, about 120-210 of 250. The owner approved it on 29-10-2026. To reproduce: scripts `bt.py`, `cmp.py`, `frente_casas.py`, `ligas_conteos.py`, `players.py` and `gasto_oddspapi.py` in the notes of the 29-10-2026 session (not in the repository).

**Turkey as a full league** (30-10-2026, at the owner's request), the same as Portugal and Belgium: football-data's 1,109 matches since 2023-24 now have FotMob's details (xG, stats, referee, XI and players; Understat doesn't cover it). 2024-26 walk-forward on the before and after copies, with `main`'s code of 30-10-2026; `apuestas backtest` evaluates the eight leagues by default.

| 1X2 log-loss (same matches) | Matches | Before | After | Difference |
|---|---|---|---|---|
| Turkey | 643 | 0.9523 | 0.9517 | −0.0006 ± 0.0010 |
| The seven earlier ones | 4,719 | 0.9710 | 0.9710 | 0.0000 ± 0.0000 |
| Cups | 1,030 | 0.9627 | 0.9623 | −0.0004 ± 0.0002 |

With ρ estimated with eight leagues instead of seven (which also changes in production), the seven earlier ones −0.0002 ± 0.0001 and the cups +0.0003 ± 0.0003.

**In Turkey the model predicts worse than the bookmakers**: log-loss 0.9497 against bet365's 0.9378 and Pinnacle's 0.9365 (625 matches with both; model − bet365 +0.0119 ± 0.0045, before the change +0.0122 ± 0.0044). It's the same as in the Bundesliga (+0.0105 ± 0.0036) and slightly more than in LaLiga (+0.0071 ± 0.0037). Backtest bets (model only, value ≥ 3 %): from 326 with ROI −13.7 % to 337 with −9.6 % (CLV +2.1 % → +2.6 %); with the market blend, 30 bets with −22.8 % (very small sample).

Stats (improvement per match against the league average, after): corners per team +0.112, shots +0.307, on target +0.230, fouls +0.246, cards +0.037. The referee weighs more than in any other league: cards +0.019 ± 0.005 and fouls +0.027 ± 0.007. FotMob and football-data differ in 25 % of team shots (FotMob +0.2) and in 13 % of fouls; FotMob rules.

Players out of sample (as in Portugal and Belgium): cut-off 15-01-2026, 4,497 player-matches, goals 269 expected / 254 real, assists 195 / 186, shots 2,820 / 2,693, goal log-loss 0.1778 (average rate 0.2172); cut-off 23-07-2026, 2,036, goals 129 / 116, assists 89 / 81, shots 1,313 / 1,431, goal log-loss 0.1816 (0.2186). Goals come out somewhat high (1.06-1.11), in line with a goals model that lags behind the bookmakers in Turkey.

OddsPapi: with eight competitions it was already 2 requests per bookmaker almost every day and the API allows 5 tournaments per request, so the ninth adds 0 to 10 a month (70-112 with the 2025-26 calendar). The owner approved it on 30-10-2026.

**Eredivisie as a full league, on trial** (21-11-2026, at the owner's request: of the leagues with enough data to measure the model, the one recommended first). Like Turkey: football-data's 1,233 matches since 2023-24 now have FotMob's details (1,035 played, all with xG, stats, referee, XI and players). It goes in **without the bet of the day** (`Competition.picks=False`) until the owner decides, in view of these figures. 2024-26 walk-forward with the nine leagues, on the same database before and after the download (`apuestas backtest --ligas EPL,BUN,LAL,SA,L1,POR,BEL,TUR,NED`, 5,971 → 5,977 matches):

| 1X2 log-loss, Eredivisie (609 matches) | Model | bet365 | Pinnacle | 25/75 blend |
|---|---|---|---|---|
| Before (results, football-data stats and closing odds only) | 0.9635 | 0.9629 | 0.9603 | 0.9601 |
| After (with FotMob's xG and details) | 0.9630 | 0.9629 | 0.9603 | 0.9600 |

The model ends up level with bet365 and behind Pinnacle, as in Portugal and Belgium; the other eight leagues don't change (to four decimals), nor do team goals (blend 0.5432). Bets in the Eredivisie: model only 375 → 358, return −1.7 % → −0.1 %, CLV +2.6 % → +3.1 %; with the market blend 28 → 29, −3.5 % → +4.9 % (too few to tell anything). With FotMob's stats from one more league, the count models improve a little in all leagues (log-likelihood per team over the league average: offsides 0.1308 → 0.1283 worse, cards 0.0633 → 0.0645, shots and corners the same).

**National teams: UEFA Nations League** (10 and 11-11-2026, at the owner's request; `experimentos/validacion/selecciones.py`). It goes in as a full competition for analysis, **without bet of the day and without player markets** (owner's decisions), with the European qualifiers for the 2026 World Cup, the 2026 World Cup and Euro 2024 as history (683 matches, 86 national teams; `docs/fuentes.md`). What changes compared with a club:

- **No closing odds or market ratings.** football-data doesn't cover national teams, so their strength comes only from FotMob goals and xG, with between 14 and 35 matches per European national team over three years (median 19; before requesting the history, 25-35 was estimated). The usual prudence rules apply by themselves: `market_matches = 0`, so confidence carries the minimum factor (×0.6) and the probability is blended with the bookmaker's (25 % model). The bet also carries the reason "Selecciones: no entra en la apuesta del día ni pasa el corte…" ("national teams: not part of the bet of the day and never clears the threshold") and never gives "APOSTAR" ("BET").
- **It can't be measured against bet365.** There are no free historical national team odds. The only possible reference is the simplest one: both national teams as the average team, with home advantage (`logloss_equipos_iguales`, new in `apuestas backtest --selecciones`). Beating it is a very low bar (Spain against San Marino isn't an even match): **it doesn't say the model is useful for betting.**
- **The same model as the clubs.** National teams never cross with clubs, but they share the goals average, the general home advantage (with its deviation per competition: Nations League −0.013 over 0.217), ρ, the dispersion of the counts and the referees. The World Cup and the Euros go as a neutral venue.
- **Players.** `fit_players` leaves out national team matches: club projections don't change (5,512 players before and after) and there are no props for national teams (what's known about the player comes from their club, with another role and other team-mates). Line-ups are used for the XI adjustment, against the national team's usual XI.

*Clubs, before and after training with the national teams* (`apuestas backtest --europa`, 2024-08 → 2026-06, 5,362 matches with odds):

| | Without national teams | With national teams |
|---|---|---|
| Model 1X2 log-loss (bet365 0.9645, Pinnacle 0.9645, blend 0.9641) | 0.9674 | 0.9674 |
| By league (EPL, BUN, LAL, SA, L1, BEL, TUR) | 0.9933 / 0.9810 / 0.9632 / 0.9673 / 0.9671 / 1.0035 / 0.9517 | the same |
| Portugal | 0.9189 | 0.9188 |
| Champions League / Europa League / Conference | 0.9011 / 0.9856 / 1.0149 | 0.9010 / 0.9856 / 1.0146 |
| Model-only bets | 3,306, ROI −4.38 %, CLV +1.11 % | 3,305, ROI −4.50 %, CLV +1.10 % |
| Model + market bets | 188, ROI −11.69 %, CLV +2.51 % | the same |
| Shots / corners / cards / fouls / offsides (total improvement per match against the average) | 0.0467 / 0.0153 / 0.0399 / 0.1675 / 0.0488 | 0.0476 / 0.0156 / 0.0396 / 0.1676 / 0.0503 |

Nothing changes beyond the fourth decimal: a single bet out of 3,306 is different. The model still doesn't beat bet365.

*National teams: model against "equal teams"* (1X2 log-loss, weekly walk-forward; lower is better):

| Tournament and window | Matches | Model | Equal teams | Improvement |
|---|---|---|---|---|
| Nations League 2024-25 (2024-08 → 2026-06; starts with almost no history) | 133 | 0.9791 | 1.0822 | +0.103 ± 0.061 |
| 2026 World Cup qualifiers | 204 | 0.8135 | 1.0576 | +0.244 ± 0.066 |
| 2026 World Cup, June | 55 | 0.9238 | 1.0846 | +0.161 ± 0.111 |
| **Nations League 2026-27** (2026-07 → 2026-11, already with the World Cup and the qualifiers) | 104 | 0.9521 | 1.0991 | +0.147 ± 0.065 |
| 2026 World Cup, July | 25 | 0.7771 | 1.0570 | +0.280 ± 0.086 |

*Stats in the Nations League* (total improvement per match against the average): in 2024-25 (168 matches), shots +0.059 ± 0.042, cards +0.048 ± 0.041 and fouls +0.160 ± 0.097; on target +0.022 ± 0.044 and corners −0.008 ± 0.028 aren't distinguishable from the average. In 2026-27 (104), **none is distinguishable from the average**: shots +0.045 ± 0.065, on target −0.007 ± 0.061, corners +0.017 ± 0.025, cards −0.024 ± 0.059 and fouls +0.030 ± 0.077. With so few matches per national team, the corners and cards prices that come out "with value" in these matches can't be trusted (and they do come out: for 12-11, 99 value bets were saved, in cards, goals and corners; none clears the threshold).

*National teams' xG in the goals model*: it goes in, as in the leagues (`GOALS_XG_SKIP` only leaves out the Europa League and Conference one). Paired on the same matches, with xG − without xG: Nations League +0.027 ± 0.027 (slightly worse with xG, at the edge of the margin), qualifiers 0.000 ± 0.026, World Cup −0.036 ± 0.052 (better with xG) and the 521 together +0.007 ± 0.018. Not distinguishable: it's left as in the leagues and measured again with the November window.

OddsPapi: the Nations League is a single tournament and is played during club breaks, so it's 1 request per bookmaker and day: about 14 per window (7 days × Betano and Pinnacle). No pre-match CLV, because its bets never clear the threshold. The owner approved it on 10-11-2026 (42 of 250 had been used; 46 after the first download).

**Corners of the big home team in the Champions League against Pinnacle** (22-10-2026). With the goals strength as a guide and the cups' stats, the model still gave the home team about 0.7 fewer corners than Pinnacle in Betis-Feyenoord (4.6-4.7 against 5.3-4.1; Betano 5.4-4.1) and Bayern-Arsenal (4.8-4.1 against 5.5-4.2; Betano 5.7-4.1). The level per league, more shrinkage (K 40) and a home bias across the whole Champions League had already been ruled out.

*Where each number comes from.* Bayern-Arsenal: 4.79 = exp(mean 1.457 + home 0.202 + Bayern attack 0.500 − Arsenal defence 0.593). Arsenal is the team that concedes the fewest corners (2.8 at home and 3.8 away in the Premier League) and, in the goals model, stronger than Bayern (1.83 against 1.62; model 1X2 38/24/38, Pinnacle 43/26/32). Betis-Feyenoord: with the goals strength alone it came out 5.2-4.3; each team's deviations took it to 4.6-4.7, because Betis win fewer corners in LaLiga than their strength warrants (−0.08 dominance) and Feyenoord more in the Eredivisie (+0.13). Their goals strength is almost the same (0.63 and 0.67), so the model saw them as even, and Pinnacle didn't (1X2 60/20/20).

*Ruled out, with the real corners* (weekly walk-forward 2024-08 → 2026-10, the same production model; 2,344 league matches, 414 Champions League and 738 from the other two cups):
- **A big-home-team bias.** Real against expected in the Champions League: home +1.8 % and away −0.6 %. By home team strength no pattern emerges: 0.5-1.0 → −12.7 % ± 4.7 %; 1.0-1.4 → +9.7 % ± 5.3 %; over 1.4 → +1.7 % ± 7.1 %. Between two big teams (strength ≥ 1), +8.5 % ± 5.9 % (93 matches) and in the leagues +4.9 % ± 6.6 % (63): noise. This season (36 Champions League matches up to 19-10) the home team wins 16 % **fewer** than expected, the opposite of what Pinnacle says.
- **That each team's deviation doesn't hold in Europe.** With m(λ) = strength only × (model / strength only)^λ, the λ that predicts best in cross-league Champions League matches is 0.91 ± 0.24 (1 = the deviation holds in full); in the cups, 0.75 ± 0.28. Removing it in those matches makes corners per team worse (−0.024 ± 0.014 in cross-league Champions League). Feyenoord in particular underperform the model in Europe (−10 % corners for), but a per-team "Europe" effect would be noise for almost everyone.
- **A different slope per league** (the strong team dominating more in a weak league): none is distinguishable from the general one (Eredivisie +0.06 ± 0.05, LaLiga −0.02 ± 0.04, Premier League +0.09 ± 0.05).
- **A shorter memory.** Bayern have 9.7 corners per match in the 2026-27 Bundesliga (the model expected 7.3), and Pinnacle seems to weigh that streak more: with a 120-day half-life instead of 240, the per-team error against Pinnacle drops from 0.087 to 0.078 across the 41 matches and Bayern rise to 5.1. But it predicts real corners worse: Champions League per team −0.0058 ± 0.0042, cups −0.0063 ± 0.0028, and this season, cross-league Champions League −0.038 ± 0.019. With 180 days, almost the same as now.

*The cause: the goals model's strength difference.* If the strength difference between the two were that of Pinnacle's 1X2, Betis-Feyenoord would come out 5.1-4.2 and Bayern-Arsenal 5.0-3.9. The bookmakers see the difference better than the goals model (we don't beat the market in 1X2), and the counts inherit it. Moving the split towards that of the match's closing 1X2 (section 3) was tried in the same walk-forward, with Pinnacle or bet365 closing odds from 14 leagues (the three main ones and 11 "light" leagues that bring stats); in the Champions League and the other cups there are no saved closing odds, so there it can't be measured with results. Log-likelihood difference per team and match against the current model (the total stays the same by construction: −0.0001 ± 0.0000 or less):

| 1X2 weight | Corners: 3 leagues (2,342) | Corners: other 11 (8,227) | Shots: 3 leagues | Shots: other 11 | On target: 3 leagues | On target: other 11 |
|---|---|---|---|---|---|---|
| 0.5 | +0.0062 ± 0.0017 | +0.0083 ± 0.0009 | +0.0149 ± 0.0025 | +0.0161 ± 0.0014 | +0.0085 ± 0.0019 | +0.0106 ± 0.0011 |
| **0.75 (applied)** | **+0.0074 ± 0.0026** | **+0.0105 ± 0.0013** | **+0.0183 ± 0.0037** | **+0.0196 ± 0.0021** | **+0.0098 ± 0.0028** | **+0.0126 ± 0.0016** |
| 1 | +0.0075 ± 0.0034 | +0.0115 ± 0.0018 | +0.0190 ± 0.0050 | +0.0200 ± 0.0028 | +0.0091 ± 0.0037 | +0.0124 ± 0.0022 |

The improvement is concentrated where the bookmaker and the goals model disagree a lot (|δ| > 0.2, 317 matches: corners +0.107 ± 0.020, shots +0.167 ± 0.032 per match), which is common in the Champions League (Betis-Feyenoord 0.18; Manchester City-AEK 0.34). It's the same in all three seasons (corners in the other 11 leagues, with weight 1 and without fixing the total: 2024-25 +0.0121 ± 0.0027, 2025-26 +0.0109 ± 0.0026, 2026-27 +0.0096 ± 0.0062). With `apuestas backtest --europa` (2,132 league matches, against `--no-count-market`): corners per team −4.6526 → −4.6458 (+0.0068), shots −5.8053 → −5.7897 (+0.0156), on target −4.3054 → −4.2967 (+0.0087); the totals, the 1X2 (0.9801), the bets, cards and fouls, identical.

Against the saved odds (model up to 20-10; δ from Pinnacle's 1X2), error of each team's corners mean:

| Corners, error per team | Leagues | Champions, known teams | Champions, little data | All |
|---|---|---|---|---|
| Pinnacle (41 matches: 25 / 9 / 7), before | 0.073 | 0.119 | 0.082 | 0.087 |
| **Pinnacle, with the 1X2 (0.75)** | **0.072** | **0.070** | **0.075** | **0.072** |
| Betano (47 matches: 29 / 11 / 7), before | 0.060 | 0.129 | 0.066 | 0.082 |
| **Betano, with the 1X2 (0.75)** | **0.059** | **0.091** | **0.077** | **0.071** |

In the Champions League, the error of the home − away difference against Pinnacle drops from 0.99 to 0.59 corners. Teams with little data barely change (and in their markets it's already blended with the bookmaker, section 6). In the 17 of those matches already played nothing is distinguishable (−0.003 ± 0.024 per match against the current model; they're very few).

| Corners (home-away) | Pinnacle | Betano | Before | With the 1X2 | Real |
|---|---|---|---|---|---|
| Betis-Feyenoord | 5.3-4.1 | 5.4-4.1 | 4.6-4.7 | 5.0-4.3 | 4-4 |
| Bayern-Arsenal | 5.5-4.2 | 5.7-4.1 | 4.8-4.1 | 4.9-4.0 | 3-5 |
| Manchester City-AEK | 7.8-2.2 | 7.9-2.3 | 6.5-3.1 | 7.1-2.5 | 8-3 |
| Porto-PSV | 5.6-4.2 | 5.9-4.0 | 5.2-4.2 | 5.4-4.0 | 2-3 |

*What remains.* In Bayern-Arsenal the strength difference barely changes (δ = 0.07): what's missing is the total (Pinnacle 9.7 corners, the model 8.9), that is, Bayern's streak and the fact that Arsenal's matches have few corners. The data doesn't support raising it (shorter memory, above), so it isn't touched. In the real analysis, with the confirmed line-ups, "Bayern under 3.5 corners" at 4.25 goes from +57 % to +42 %: it still comes out with value because of that total (Bayern won 3).

To reproduce: scripts in the session notes folder (`wf_cor.py` and `wf_stat.py` for the walk-forward, `cmp_cor.py`, `mkt_final.py` and `bins.py` for the figures, `pindiag.py` and `played.py` for the bookmakers), and `apuestas backtest --europa` with and without `--no-count-market` (outputs in `var/backtests/conteos_mercado_{antes,despues}_2024_2026.json`).


**2026-27 shots: each league's recent level** (22-10-2026). Since July 2026 there are more shots in almost every league. Shots per team in August-October of each season (database; FotMob and football-data agree):

| August-October | Premier League | Bundesliga | LaLiga | Serie A | Ligue 1 | Champions League |
|---|---|---|---|---|---|---|
| 2023-24 | 13.5 | 13.7 | 12.6 | 12.5 | 12.7 | 13.8 |
| 2024-25 | 13.5 | 13.8 | 12.1 | 12.8 | 12.4 | 13.3 |
| 2025-26 | 11.9 | 13.3 | 12.4 | 12.3 | 12.4 | 13.6 |
| 2026-27 | 13.7 | 15.6 | 13.5 | 14.6 | 13.7 | 14.8 |

The same in the others: Eredivisie 14.0 → 15.0, Scotland 12.4 → 14.4, Turkey 12.9 → 14.0, 2. Bundesliga 13.5 → 15.2; only Portugal doesn't change. On target goes up in the Bundesliga (4.6 → 5.5), Serie A (4.0 → 4.9), Ligue 1, LaLiga and the Champions League, not in the Premier League. Corners barely change (Bundesliga 5.0 → 5.4; Premier League 4.9 → 4.7).

*Since when.* Weekly walk-forward (August 2024 to October 2026, the production model refitted each week with earlier data), real / expected per season:

| Real / expected | Premier League | Bundesliga | LaLiga | Serie A | Ligue 1 | Champions League | Other 11 leagues |
|---|---|---|---|---|---|---|---|
| Shots 2024-25 | 0.97 → 0.99 | 0.97 → 0.99 | 0.99 → 1.00 | 0.96 → 0.99 | 0.99 → 1.00 | 1.02 → 1.01 | 0.99 → 1.00 |
| Shots 2025-26 | 0.99 → 1.01 | 1.01 → 1.01 | 1.02 → 1.00 | 0.99 → 1.00 | 1.00 → 1.01 | 1.05 → 1.02 | 1.01 → 1.01 |
| Shots 2026-27 | 1.06 → 1.01 | 1.16 → 1.05 | 1.07 → 1.05 | 1.14 → 1.06 | 1.08 → 1.01 | 1.10 → 1.05 | 1.07 → 1.02 |
| On target 2024-25 | 0.94 → 0.98 | 0.97 → 0.99 | 0.99 → 1.01 | 0.97 → 0.99 | 1.02 → 1.00 | 1.04 → 1.03 | 0.99 → 1.00 |
| On target 2025-26 | 0.96 → 1.00 | 1.03 → 1.02 | 1.02 → 1.01 | 0.98 → 1.00 | 0.97 → 1.00 | 1.08 → 1.04 | 1.00 → 1.01 |
| On target 2026-27 | 0.98 → 0.98 | 1.15 → 1.05 | 1.07 → 1.04 | 1.16 → 1.09 | 1.08 → 1.04 | 1.17 → 1.10 | 1.05 → 1.02 |

(before → with the level). Month by month, the gap appears suddenly in August-September 2026; before, over a whole season no league deviated more than 3-4 % (the 2024-25 Premier League, Bundesliga and Serie A, in which the model expected 3 % too many). In the five leagues, per team: in 2026-27, 12.9 expected shots → 13.7 (real 14.1); in October 2026, 13.1 → 14.1 (real 14.3); on target in October, 4.5 → 4.8 (real 5.0). What's still short is mainly the start of the season (August), until the level has new matches, and shots on target in Serie A and the Champions League, which kept rising in October.

*Variants* (improvement in log-likelihood per team and match against the previous model, in the same walk-forward; positive = better):

| Variant | Shots, 5 leagues: 24-25 / 25-26 / 26-27 | On target, Champions League: 24-25 / 25-26 / 26-27 |
|---|---|---|
| The whole model with a 120-day half-life | +0.0095 / +0.0022 / +0.0306 | +0.0078 / −0.0238 / −0.0175 |
| League level, 120-day half-life (K 10) | +0.0016 / −0.0000 / +0.0172 | −0.0089 / +0.0026 / +0.0124 |
| League level, 60 days (K 10) | +0.0037 / +0.0003 / +0.0388 | −0.0142 / +0.0009 / +0.0316 |
| League level, 45 days (K 10) | +0.0042 / +0.0002 / +0.0472 | −0.0164 / +0.0000 / +0.0389 |
| 45 days, shrunk towards all, plus cup deviation | +0.0043 / +0.0003 / +0.0548 | −0.0058 / +0.0243 / +0.0640 |
| **30 days, shrunk towards all, plus cup deviation (applied)** | **+0.0050 / +0.0000 / +0.0665** | **−0.0078 / +0.0220 / +0.0714** |
| 20 days, same | +0.0054 / −0.0007 / +0.0711 | −0.0098 / +0.0244 / +0.0720 |
| Level per season (current only, K 10), plus cup deviation | +0.0014 / −0.0014 / +0.0647 | −0.0092 / +0.0228 / +0.0649 |
| Ceiling: each league and season's real deviation, known in advance | +0.0059 / +0.0010 / +0.0904 | +0.0080 / +0.0284 / +0.1224 |

- **Short memory only for the level, not for the whole model.** Shortening the half-life of the whole shots model (120 days) also helps in 2026-27, but much less and makes the Champions League worse (on target −0.024 in 2025-26 and −0.018 in 2026-27): each team's strength needs a long memory; the league level doesn't.
- **Shrunk towards all competitions** improves 2026-27 (+0.044 against +0.039 with 60 days) without changing anything before: the change is common to almost every league.
- **Cup deviation.** If the cup only takes the average of the leagues, 2024-25 shots on target get worse in the Champions League (−0.014 ± 0.003), because that year the leagues had fewer shots on target than expected and the Champions League more. With its own deviation it stays at −0.008 ± 0.004 (noise) and improves 2025-26 and 2026-27. Its half-life (120 days) and K (30) are longer than the leagues' because the Champions League has few matches and its deviation repeats from season to season.
- **30 days** is the best compromise: 20 days improves 2026-27 a little more but starts making 2025-26 and the 2024-25 Champions League worse. K between 3 and 30 barely changes anything (with 60 days: +0.042, +0.039 and +0.032 in 2026-27).
- **Per season** (every match of the current season with the same weight) gives the same in 2026-27, but makes 2025-26 and the other 11 leagues slightly worse (−0.003 ± 0.001 in 2024-26).
- **Corners**: with the same level, −0.0012, −0.0005 and −0.0019 in the five leagues and −0.023 ± 0.007 in the 2026-27 Europa League and Conference. Not applied.

Result of the applied variant, with the paired standard error (shots · on target, per team):

| Group | 2024-25 | 2025-26 | 2026-27 |
|---|---|---|---|
| 5 leagues | +0.0050 ± 0.0025 · +0.0015 ± 0.0024 | +0.0000 ± 0.0016 · −0.0002 ± 0.0028 | +0.067 ± 0.016 · +0.023 ± 0.010 |
| Champions League | +0.0027 ± 0.0052 · −0.0078 ± 0.0043 | +0.0069 ± 0.0088 · +0.022 ± 0.012 | +0.060 ± 0.026 · +0.071 ± 0.028 |
| Other 11 leagues | +0.0009 ± 0.0012 · +0.0001 ± 0.0015 (2024-26) | | +0.038 ± 0.009 · +0.008 ± 0.005 |
| Europa League and Conference | −0.0012 ± 0.0030 · −0.0052 ± 0.0029 (2024-26) | | +0.027 ± 0.016 · +0.014 ± 0.010 |

In the Europa League and the Conference, 2024-26 shots on target get slightly worse (−0.005 ± 0.003); those cups are only used for training, they aren't analysed in the dashboard.

With `apuestas backtest --europa` per season, against `--no-count-level` (log-likelihood per team and match): shots in the leagues −5.7730 → −5.7680 (2024-25), −5.7756 → −5.7758 (2025-26) and −6.0711 → −6.0047 (2026-27, 346 matches up to 21-10); on target −4.2910 → −4.2895, −4.2961 → −4.2962 and −4.4723 → −4.4501; in the Champions League, shots −6.0336 → −6.0309, −5.8715 → −5.8638 and −5.9200 → −5.8691, and on target −4.5514 → −4.5592, −4.6298 → −4.6056 and −4.6036 → −4.5384. The 1X2 (0.9708, 0.9790 and 0.9561), the bets, corners, fouls and cards, identical.

*Fouls and cards*: a 60-day league level, without cup deviation, improves the five leagues (cards +0.0051 ± 0.0021 in 2024-25 and +0.0086 ± 0.0059 in 2026-27; fouls +0.0065 ± 0.0026 in 2025-26 and +0.017 ± 0.007 in 2026-27), but makes the cups worse (cards in the 2024-25 Champions League −0.007 ± 0.004, fouls in the 2026-27 one −0.014 ± 0.014) and both go through the referee factor. The cards model also expects too many in almost every league (real / expected 0.93-1.00 in 2024-26 and 0.86-0.89 in the 2026-27 Serie A, Ligue 1 and Bundesliga). Fouls stay unapplied ("Upcoming planned improvements"); cards have carried it since 22-10-2026, with their own parameters (below, "Cards: each league's recent level").

To reproduce: scripts in the session notes folder (`nivel-liga/`: `wf.py` for the parallel walk-forward, `ana.py` for the figures, `oraculo.py` for the ceiling and `nivel_hoy.py` for today's levels), and `apuestas backtest --europa --start … --end …` with and without `--no-count-level`.

**Cards: each league's recent level** (22-10-2026). The team cards model was too high in almost every competition: in the weekly walk-forward from 2024-08 to 2026-10, 1.049 of the real figure in the leagues (Premier League 1.048, Bundesliga 1.061, LaLiga 1.020, Serie A 1.079, Ligue 1 1.045) and 1.075 in the Champions League. It's not the referee (its factor is 1.00 on average in each league), but that cards go down season after season and, within each season, from the first half to the second (Serie A 2023-24: 2.29 and 2.04 per team; 2026-27: 1.68), and the model, with a 240-day half-life, lags behind.

*First exploration* (level of the match's competition, shrunk towards 1; only the cards model, in the same walk-forward; log-likelihood difference per team and match, with the referee, against the current model; leagues: 3,849 matches, Champions League: 423):

| Variant | Leagues (expected / real) | Premier League | Bundesliga | LaLiga | Serie A | Ligue 1 | Champions League |
|---|---|---|---|---|---|---|---|
| Current model | 1.049 | | | | | | |
| 30-day level, K 20 | +0.0049 ± 0.0015 (1.027) | +0.0084 ± 0.0042 | +0.0020 ± 0.0031 | +0.0018 ± 0.0030 | +0.0086 ± 0.0032 | +0.0025 ± 0.0028 | +0.0032 ± 0.0039 |
| 30-day level, K 10 | +0.0047 ± 0.0018 (1.022) | +0.0085 | +0.0013 | +0.0013 | +0.0093 | +0.0022 | +0.0028 |
| 60-day level, K 20 | +0.0039 ± 0.0013 (1.025) | +0.0047 | +0.0023 | +0.0004 | +0.0088 | +0.0028 | +0.0038 |
| 120-day level, K 20 | +0.0032 ± 0.0009 (1.027) | +0.0028 | +0.0033 | −0.0003 | +0.0075 | +0.0024 | +0.0042 |
| 180-day level, K 20 | +0.0025 ± 0.0007 (1.032) | +0.0015 | +0.0032 | −0.0004 | +0.0061 | +0.0023 | +0.0028 |
| Only a long level (365 days) | +0.0003 ± 0.0004 (1.044) | −0.0030 | +0.0015 | −0.0008 | +0.0023 | +0.0024 | −0.0022 |
| 30 days, shrunk towards the 365-day one | +0.0049 ± 0.0015 (1.025) | +0.0078 | +0.0024 | +0.0015 | +0.0090 | +0.0029 | +0.0020 |
| Model with a 120-day half-life | −0.0009 ± 0.0012 (1.043) | −0.0013 | +0.0019 | −0.0025 | −0.0030 | +0.0013 | −0.0035 |

Short memory (30 days) for the level, yes; for the whole model, no; a long level adds nothing (each league's is already captured by its teams). What remains is mainly the lag of a level that keeps going down; month by month it's very noisy (September usually has more cards and August fewer), so it isn't adjusted by date within the season.

*With the shots level* (`fitting.count_levels`, merged the same day; the level per league goes inside the count model). Its parameters were tried on cards with `apuestas backtest --europa` against `--no-count-level` (3,504 league matches and 378 Champions League in 2024-26; 345 and 45 in 2026-27; log-likelihood difference per team and match):

| Variant | Leagues 2024-26 | Leagues 2026-27 | Champions 2024-26 | Champions 2026-27 | Leagues, with referee 2024-26 |
|---|---|---|---|---|---|
| Like shots (K 10; cups: average of the leagues plus their deviation, 120 days, K 30) | +0.0042 ± 0.0020 | +0.0105 ± 0.0093 | −0.0059 ± 0.0046 | +0.0024 ± 0.021 | +0.0050 |
| K 20 | +0.0050 ± 0.0017 | +0.0123 ± 0.0086 | −0.0043 ± 0.0043 | +0.0060 ± 0.020 | +0.0056 |
| K 20, 30-day cup deviation and K 20 | +0.0050 | +0.0123 | −0.0048 ± 0.0051 | +0.0047 | +0.0056 |
| 60 days, K 10 | +0.0028 ± 0.0015 | +0.0099 ± 0.0065 | −0.0039 ± 0.0042 | +0.0044 | +0.0034 |
| K 20, in the cups only the cup's level (30 days, K 20) | +0.0050 | +0.0123 | +0.0013 ± 0.0040 | +0.0100 ± 0.0066 | +0.0056 |
| **K 20, in the cups only the cup's (120 days, K 30; applied)** | **+0.0050 ± 0.0017** | **+0.0123 ± 0.0086** | **+0.0016 ± 0.0032** | **+0.0167 ± 0.0106** | **+0.0056 ± 0.0017** |
| First exploration (competition level, 30 days, K 20, towards 1) | +0.0041 ± 0.0016 | +0.0066 ± 0.0057 | +0.0011 ± 0.0043 | +0.0107 ± 0.0073 | +0.0047 |

- **Shrunk towards all competitions** (like shots) is better than towards 1 in the leagues, above all in 2026-27: cards go down in almost all of them at once.
- **In the cups, only the cup's level** (`cup_alone` in the cards model). With the average of the two teams' leagues, the Champions League gets worse in 2024-26 (−0.004 to −0.006), with any cup deviation: in cards, the Champions League doesn't follow its teams' leagues (in the knockouts, from February to April, there are 1.3-1.8 per team; in the leagues, 1.9-2.1).
- **Referee.** It's fitted against the model without the level (`RatingModel.expected(..., level=False)`): today's level isn't valid for matches from years ago. In the first exploration, fitting it against the level at each match's date gave the same (+0.0050 against +0.0049).

Applied variant, by league (per team, 2024-26): Premier League +0.0080 ± 0.0050, Bundesliga +0.0015 ± 0.0034, LaLiga +0.0042 ± 0.0034, Serie A +0.0078 ± 0.0034, Ligue 1 +0.0021 ± 0.0032; Europa League −0.0029 ± 0.0019 and Conference −0.0030 ± 0.0031 (not analysed in the dashboard). In 2026-27: Serie A +0.032 ± 0.024, Ligue 1 +0.033 ± 0.023, Bundesliga +0.007 ± 0.027, Premier League −0.004 ± 0.012, LaLiga −0.002 ± 0.011; Conference −0.039 ± 0.015 (18 matches). In values: cards per team in the leagues −3.3214 → −3.3165 (2024-26) and −3.2199 → −3.2076 (2026-27); total −2.1103 → −2.1053; with the referee −2.1063 → −2.1006; Champions League per team −3.2432 → −3.2415 and −3.1788 → −3.1621. The 1X2 (0.9727), the bets and the other stats, identical.

To reproduce: `wf_tarj.py` and `wf_tarj2.py` (first exploration), `ana_tabla.py` (its table), `bt_tarj2.py` + `cmp_var.py` (`apuestas backtest --europa` match by match with the cards parameters) and `medir_tarjetas.py --semanal` (players, section 4), in the notes of the 22-10-2026 session.

**The stats' own total dispersion** (29-10-2026; `apuestas backtest`, entry `<stat>+total`, and `experimentos/validacion/dispersion_total.py`). Log-likelihood of the total per match in the five leagues, 2024-26 (3,504 matches), against adding up the two teams as independent, with the paired 95 % margin:

| Stat | Total alpha | Before | After | Improvement | Honest test (2024-25 alpha, evaluated on 2025-26) |
| --- | --- | --- | --- | --- | --- |
| Shots | 0.010 | −3.1443 | −3.1373 | +0.0071 ± 0.0040 | +0.0099 ± 0.0056 |
| On target | 0.003 | −2.5052 | −2.5044 | +0.0008 ± 0.0008 | +0.0008 ± 0.0012 |
| Corners | 0.017 | −2.6174 | −2.6131 | +0.0043 ± 0.0032 | +0.0047 ± 0.0052 |
| Fouls | 0.005 | −3.0565 | −3.0535 | +0.0031 ± 0.0026 | +0.0035 ± 0.0024 |
| Cards | 0 | −2.1053 | −2.1053 | 0 | 0 |

The alphas come from the same backtest matches ("Improvement" column); the last column estimates them only with 2024-25 and measures on 2025-26, and it gives the same, so it isn't overfitting. With the fit's own alpha (in sample) the improvement was smaller: shots +0.0059, corners +0.0021, and cards −0.0006 in 2025-26. Out of sample, the team alpha comes out somewhat higher than the fit's (corners 0.084 against 0.067), but the total's is still well below half the team's, which is what adding up two independent teams amounts to. In cards the total already comes out Poisson: the teams are below a Poisson (alpha −0.07 out of sample) and the positive correlation compensates for it. The 1X2, the bets and each team's markets, identical. Against Betano (`estadisticas_betano.py`, 36 matches), the corners log-loss goes from −0.0010 ± 0.0064 to −0.0012 ± 0.0055 (model − Betano): with so few matches it isn't distinguishable. The stat handicap remains open, as it still assumes independence (with negative correlation, the difference between the two teams is wider than the model says).

**Reading**:
1. In the main markets, **bet365 is still more accurate than the model**, also with the market ratings. Now the model is much closer (which is what professionals do), but there's no profitable strategy in 1X2, goals or handicap. With the model so close to the market, the few "value bets" that remain are mostly noise: the ROI doesn't improve even though the CLV does a little.
2. bet365 almost never pays more than Pinnacle's fair probability in 1X2 or goals 2.5 (4 cases in two years), so comparing bookmakers doesn't work with bet365 in those markets.
3. Pinnacle's closing odds (0.963) are much better than its opening odds (0.976): a lot of information arrives between the opening and the match (line-ups, news). The XI quality index only captures part of it (β = 0.10).
4. Where the model does add information (fouls, shots, cards, players) is exactly where the bookmakers are less precise. There, Betano's odds have to be compared with the **minimum odds** the system gives. The referee helps with cards in LaLiga, Serie A and the Bundesliga, not in the Premier League, and with fouls in Ligue 1.

To reproduce: `apuestas backtest --lineups --europa --out var/backtests/x.json` (since 21-10-2026 it evaluates the full leagues by default; `--ligas EPL,BUN,LAL` for the earlier figures; `--market-weight 0` for the model without market; `--no-count-strength` for stats without goals strength, `--no-count-market` for shots and corners without the bookmaker's 1X2, `--no-count-level` for shots, on target and cards without each league's recent level, `--count-l2 1` for the earlier fixed L2 and `--no-home-by-league` for a single home advantage).

## 8. Weekly summary: surprise against expectations (`models/surprise.py`, `services/weekly.py`)

It doesn't change the model or the bets (no backtest needed): it sums up each week who beat expectations.

- **Score of each item**: `P(X < real) − P(X > real)` with the expected distribution, from −1 to +1 (0 = as
  expected). The margin counts: with 9.9 expected corners, 10 adds +0.09, 12 +0.43, 15 +0.77 and 6 −0.65.
- **Result**: `(points − expected points) / 3`, with the no-vig 1X2. Winning with a 15 % probability adds
  +0.77; winning with 75 %, +0.19; drawing as that favourite, −0.47.
- **Teams, against the bookmaker** (the last price of each type before kick-off; closing first):
  - Result: 1X2 from Pinnacle, Betfair, bet365, Betano or the average, in that order; if there's none, the preview's.
  - Each team's goals and corners: the main line (the closest to 50 % without margin) from Pinnacle or Betano. With
    that line and its probability, the mean of a Poisson (goals) or of the model's negative binomial (corners, with
    its alpha) is solved for. Without a team goals line, the goals implied by the 1X2 and the over/under 2.5
    (`fitting.prematch_market_goals`); if not that either, the model's preview.
  - Shots on target don't count: no bookmaker prices them.
- **Players, against the model's preview** (`services/predictions.py`): shots and shots on target (negative
  binomial, alpha 0.15), goals and assists (Poisson). The rate is adjusted to the minutes played (`λ × minutes /
  expected minutes`), to measure how they played and not whether they made the XI by surprise. 30 minutes are needed.
  Goalkeepers and defenders with 60 minutes or more also add the goals conceded against the opponent's goals
  yardstick, with the sign reversed.
- **Week**: the sum of the matches (matches played and the average are also shown). XI in a 4-3-3 by
  position.
- **Limits**: each item has a ceiling (a goal with λ 0.08 adds +0.92 and two +0.997), so the detail shows the real
  and the expected figures. Adding up favours whoever played two matches. The player of the week is usually a
  forward: they have more items with upside. A good week is partly luck: it doesn't predict the next one.

### Month, radar and warnings (`services/radar.py`, since 29-10-2026)

- **Month**: the 4 full weeks ending in the chosen week, with the same score (`weekly.score_range`).
  It opens when its 4 weeks have a preview (the first, from 26-10 to 22-11-2026).
- **Radar**, over the last 28 days: a team is **on a hot streak** with a sum of +1.0 or an **upset win** (winning
  when the yardstick's no-vig 1X2 gave 25 % or less) and **on a cold streak** with −1.0 or a **slip** (losing at 60 %
  or more). Players on a hot streak: +1.5 and 90 minutes. Key players: up to 2 of the team's players with +1.5 in
  their matches. At most 8 per list.
- **Warnings**: the radar card of each team in an upcoming match, with or without its key players in the XI. **They
  don't change the probability, the confidence or the threshold**: it still has to be measured whether those who
  surprise do it again.
- **Do surprises repeat? No** (measured on 29-10-2026 with `experimentos/sorpresas/repiten.py`: 11,352 team-matches
  since 2023-07 in the six competitions, result against the pre-match no-vig 1X2). In the next match, the result's
  score against the bookmaker is +0.000 ± 0.013 on a hot streak (n = 3,322; they win 37.7 % against the bookmaker's
  37.8 %), +0.000 ± 0.021 on a hot streak with an upset win (30.5 % against 31.0 %), −0.003 ± 0.014 on a cold streak
  and +0.034 ± 0.039 on a cold streak with a slip (if anything they bounce back, they don't keep falling). The
  bookmaker already accounts for it: the warning stays a warning, without touching the confidence, and says so.
- **Why it failed**: the preview against what happened in the lost bet of the day, with the same score, and whether
  the radar flagged either team when the bet was generated. Real example: Sassuolo +1 (3-way) on 27-10
  lost 2-6; Lazio were on a hot streak after winning 0-3 in Turin at 17 % and their key player Kenneth Taylor played.

## Upcoming planned improvements

- **Proposals from the October 2026 audit** ([auditoria-modelo.md](auditoria-modelo.md)), reviewed with the database on 29-10-2026: applied the value of quarter lines, the fixed copy of what was announced and the total's own dispersion in the counts (section 3); measured and not applied dynamic strength (section 1, −0.0018 ± 0.0022), stacking with the market and choosing by the probability of value (section 6). Later the same day: per-league home advantage applied (section 1), draw calibration measured and not needed, and the model-free comparison of Betano against no-vig Pinnacle built (section 6). Still untested: shots on target as an observation of dynamic strength and Kelly shrunk with the variance (it needs a variance per prediction, which dynamic strength would provide).
- Save Champions League 1X2 odds before each match (OddsPapi's have been saved since 19-10-2026) to measure with results the split of shots and corners moved by the 1X2 in the cups, which today is only measured in the leagues.
- Save the history of predicted XIs to calibrate their β separately.
- XI quality index: **measured on 14-11-2026** (section 7, "Other XI quality indices"). Recent rating and xG + xA add nothing; counting usual starters alongside the current index grazes its margin (−0.0013 ± 0.0012) and doesn't go in. Repeat `experimentos/validacion/calidad_once.py` at the end of the 2026-27 season.
- Props backtest when there are saved Betano odds: OddsPapi doesn't download player props, so today there's nothing
  to compare them with.
- **Corners and cards against Betano** (measured on 29-10-2026 with `experimentos/validacion/estadisticas_betano.py`, 34
  matches with a preview and Betano odds): the model's log-loss minus Betano's no-vig one +0.0016 ± 0.0063
  in corners (1,128 lines) and +0.0050 ± 0.0134 in cards (576); betting what the model sees with value ≥ 3 % returns
  −15 % ± 20 % in corners (204) and +2 % ± 11 % in cards (223), with optimistic intervals because a match's lines
  are correlated. Neither clearly better nor worse than Betano: they stay out of the bet of the day
  (`pick_allow_stat_markets=False`). Repeat when there are about 150 matches (around December).
- Team cards in 2026-27: with each league's level, Serie A and the Bundesliga stay at 1.04-1.05 and the Champions League at 1.09 (still somewhat high: cards keep going down), and the Premier League at 0.94 (in 2026-27 it goes up, the opposite of the others, and the level shrinks it towards everyone's). Measure again when there are more matches this season.
- Substitutes in the confirmed XI: **adjusted on 29-10-2026** to what was measured (9,701 substitutes from July to October 2026: they come on 44.3 % of the time and play 20.1 min; `analysis.SUB_PLAY_RATE` and `SUB_MINUTES`). A substitute's expected minutes go down from 12.1 to 8.9, what they really play; before, all their markets came out ~36 % high. Since 29-10-2026 their markets are **conditional on playing** (`PlayerProjection.play_prob`): bets on a player who doesn't come on are voided, so the probability is that of what they do if they play (λ / probability of playing; in cards, the probability divided by that of playing). Before, it counted that they might not come on and "Yes" came out low. Expected minutes and the split of the team's figures don't change. With the confirmed XI, the probability of playing is 1 for starters and 0.443 for substitutes; without a published XI it stays at 1 (the average minutes already count the matches they didn't play). Checked with the saved previews (`experimentos/validacion/suplentes.py`, 196 substitutes since 24-10, 78 came on): expected shots if they play 29.1 against 43 real (unconditional, 24.7), on target 10.0 against 15 and goals 3.0 against 5. It improves, but still comes up short: the substitutes who came on played 23.9 min (20.1 assumed) and perhaps shoot more per minute than starters. Repeat with a few hundred substitutes.
- Minutes without a line-up for a player coming back from a long injury: the matches they were out count as 0 (section 4). With the absences history saved since 19-10-2026 they can be removed from their window; measure it with `medir_minutos.py` when there are a few months.

