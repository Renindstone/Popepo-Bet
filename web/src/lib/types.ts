// Formas de las respuestas de la API FastAPI (src/apuestas/api/app.py y services/queries.py)

export type Competicion = "EPL" | "BUN" | "LAL" | "UCL" | string;

export interface MatchSummary {
  match_id: number;
  competition: Competicion;
  kickoff_local: string; // "lun 19/10 14:00" (hora de Lima)
  home: string;
  away: string;
  referee: string | null;
  lineups: "predicted" | "confirmed" | null;
}

export type Probs1x2 = { home: number; draw: number; away: number };

export interface BetEval {
  market: string;
  selection: string;
  line: number | null;
  bookmaker: string;
  odds: number;
  model_prob: number;
  sharp_prob: number | null;
  prob: number;
  fair_odds: number;
  ev: number;
  stake_pct: number;
  confidence: number;
  player_id: number | null;
  reasons: string[];
}

export interface ValueBet extends BetEval {
  match_id: number;
  label: string;
  match: string;
  qualifies: boolean;
}

export interface PropMinOdds {
  market: string;
  selection: string;
  line: number | null;
  player_id?: number;
  player?: string;
  prob: number;
  fair_odds: number;
  min_odds: number;
  match_id?: number;
  match?: string;
}

export interface PickOfDay {
  pick_id?: number;
  match_id?: number;
  match: string;
  competition?: string;
  kickoff_local?: string;
  market: string;
  selection: string;
  line: number | null;
  bookmaker?: string;
  odds: number;
  prob?: number;
  fair_odds?: number;
  ev: number;
  confidence?: number;
  stake_pct?: number;
  stage?: string;
  reasons?: string[];
  // Días pasados (leídos de la BD)
  result?: string | null;
  clv?: number | null;
}

export interface DayMatch {
  match_id: number;
  competition: Competicion;
  kickoff_local: string; // "14:00"
  home: string;
  away: string;
  stage: string;
  difficulty: { home: string; away: string };
  "1x2": Probs1x2;
}

/** Días de hoy en adelante: informe completo. Días pasados: solo lo guardado en la BD. */
export interface PicksReport {
  date: string;
  pick_of_day: PickOfDay | null;
  value_bets: (ValueBet | PastValueBet)[];
  props_to_check?: PropMinOdds[];
  matches?: DayMatch[];
  notes?: string[];
}

export interface PastValueBet {
  match: string;
  market: string;
  selection: string;
  line: number | null;
  odds: number;
  ev: number;
  status: string;
  result: string | null;
}

export interface StatSummary {
  expected: { home: number; away: number; total: number };
  over: Record<string, number>;
}

export interface MissingRegular {
  player_id: number;
  name: string;
  position: string | null;
  kind: string;
  expected_return: string | null;
  start_rate: number;
  quality: number;
}

export interface LineupAdjustment {
  source: string;
  attack_mult: number;
  defence_mult: number;
  xi_attack: number | null;
  base_attack: number | null;
  xi_defence: number | null;
  base_defence: number | null;
  missing_regulars: MissingRegular[];
  notes: string[];
}

export interface TeamContext {
  rest_days: number | null;
  matches_last_14d: number;
  next_match_days: number | null;
  next_match_competition: string | null;
  rotation_risk: "baja" | "media" | "alta";
  notes: string[];
}

export interface RefereeInMatch {
  name: string;
  matches: number;
  cards_per_match?: number;
  expected_cards_per_match?: number;
  cards_factor?: number;
  fouls_per_match?: number;
  fouls_factor?: number;
  last_match?: string;
  note?: string;
}

export interface PlayerProjection {
  player_id: number;
  name: string;
  team_id: number;
  position: string | null;
  expected_minutes: number;
  start_prob: number;
  expected: {
    shots: number;
    shots_on_target: number;
    goals: number;
    /** Asistencias esperadas (de partidos con xA); puede faltar en modelos entrenados antes de añadirlas */
    assists?: number;
    fouls_committed: number;
    yellow_cards: number;
  };
}

export interface MatchAnalysis {
  match_id: number;
  competition: string;
  kickoff_utc: string;
  kickoff_local: string; // "2026-10-20 14:00"
  home: string;
  away: string;
  stage: string;
  model: {
    expected_goals: { home: number; away: number };
    "1x2": Probs1x2;
    fair_odds_1x2: Probs1x2;
    btts_yes: number;
    over_goals: Record<string, number>;
    asian_handicap_home: Record<string, number>;
    top_scores: { score: string; prob: number }[];
    stats: Record<string, StatSummary>;
  };
  difficulty: {
    home: { base: string; ajustada: string; goal_diff: number };
    away: { base: string; ajustada: string; goal_diff: number };
  };
  lineups_and_absences: { home: LineupAdjustment; away: LineupAdjustment };
  context: { home: TeamContext; away: TeamContext };
  referee: RefereeInMatch | null;
  data_quality: {
    lineup_status: string;
    lineup_factor: number;
    sample_factor: number;
    weighted_matches_min: number;
    referee_known: boolean;
    model_as_of: string;
  };
  value_bets: (BetEval & { label: string })[];
  props_min_odds: PropMinOdds[];
  players: PlayerProjection[];
}

export interface Evaluation extends BetEval {
  match: string;
  bet: string;
  verdict: "APOSTAR" | "valor pequeño o poca confianza" | "NO apostar" | string;
  min_odds_for_value: number | null;
  lineup_status: string;
}

export interface Absence {
  player: string;
  position: string | null;
  kind: string;
  reason: string | null;
  expected_return: string | null;
  source: string;
  market_value_m: number;
}

export interface TeamAbsences {
  team: string;
  absences: Absence[];
}

export interface RefereeProfile extends RefereeInMatch {
  referee: string;
  profile: string;
  upcoming: string[];
}

export interface PlayerDetail {
  player: string;
  position: string | null;
  team: string | null;
  market_value_m: number;
  season_rating: number | null;
  per90: Record<string, number> | null;
  minutes90: number | null;
  starts: number | null;
  next_match?: string;
  projection?:
    | (PlayerProjection & {
        p_shots_over_0_5: number;
        p_shots_over_1_5: number;
        p_shots_over_2_5: number;
        p_sot_over_0_5: number;
        p_sot_over_1_5: number;
        p_goal: number;
        p_assist: number;
        p_goal_assist: number;
        p_card: number;
      })
    | null;
  note?: string;
}

export interface Bankroll {
  /** Banca inicial declarada por el usuario (base del stake sugerido y de los límites) */
  bankroll: number;
  currency: string;
  /** Banca inicial + beneficio de todas las apuestas liquidadas */
  current: number;
  total_profit: number;
  day_profit: number;
  week_profit: number;
  pending_bets: number;
  pending_stake: number;
  daily_loss_limit: number;
  weekly_loss_limit: number;
  warnings: string[];
  as_of: string;
}

export interface Aggregate {
  bets: number;
  staked: number;
  profit: number;
  roi: number | null;
  hit_rate: number | null;
  avg_odds: number | null;
  avg_clv: number | null;
}

export interface Performance {
  total: Aggregate;
  market: Record<string, Aggregate>;
  competition: Record<string, Aggregate>;
  bookmaker: Record<string, Aggregate>;
  odds_band: Record<string, Aggregate>;
  bankroll: Bankroll;
}

export interface UserBetLeg {
  match: string;
  match_id: number;
  market: string;
  selection: string;
  line: number | null;
  odds: number | null;
  block_odds: number | null;
  player: string | null;
  result: string | null;
}

export interface UserBet {
  bet_id: number;
  match: string;
  market: string;
  selection: string;
  line: number | null;
  odds: number;
  stake: number;
  bookmaker: string;
  result: string | null;
  profit: number | null;
  clv: number | null;
  /** Solo en combinadas y Bet Builders (market = "combo") */
  legs?: UserBetLeg[];
}

export interface RegisteredBet {
  bet_id: number;
  match: string;
  market: string;
  selection: string;
  line: number | null;
  odds: number;
  stake: number;
  model_prob: number | null;
  ev: number | null;
  bankroll: Bankroll;
}

/** Contador de aciertos de la apuesta del día desde el inicio (GET /picks/record) */
export interface PickRecord {
  since: string | null;
  settled: number;
  hits: number;
  misses: number;
  pushes: number;
  pending: number;
  hit_rate: number | null;
  profit_units: number;
  roi: number | null;
}

export interface PickHistory {
  picks: number;
  profit_units: number;
  roi: number | null;
  hit_rate: number | null;
  avg_clv: number | null;
  last: {
    date: string;
    match: string;
    market: string;
    selection: string;
    line: number | null;
    odds: number;
    result: string | null;
    clv: number | null;
  }[];
}

export interface DataStatus {
  sources: Record<string, { task: string; finished_at: string | null; status: string }>;
  counts: {
    matches: number;
    matches_with_details: number;
    players: number;
    active_absences: number;
    odds_rows: number;
  };
  model_as_of: string | null;
}

// --------------------------------------------------------------------------- capturas de cuotas

export type CaptureStatus = "pendiente" | "procesando" | "evaluada" | "lista" | "no_evaluable" | "error";

export interface ComboLeg {
  market: string;
  selection: string;
  line: number | null;
  player: string | null;
  text: string | null;
  label: string;
}

export interface ComboBlock {
  match: string;
  match_id: number | null;
  competition?: Competicion;
  kickoff_local?: string;
  odds: number | null;
  legs: ComboLeg[];
  prob: number | null;
  fair_odds: number | null;
  ev: number | null;
  reason: string | null;
  notes: string[];
}

export interface CaptureCombo {
  total_odds: number | null;
  prob: number | null;
  fair_odds: number | null;
  ev: number | null;
  evaluable: boolean;
  verdict: "con valor" | "sin valor" | "no evaluable" | "sin cuota para comparar" | string;
  /** Alguna selección (córners, tarjetas, remates…) se combinó como si no dependiera del resultado */
  approximate?: boolean;
  blocks: ComboBlock[];
}

export interface CaptureEval extends BetEval {
  verdict: Evaluation["verdict"];
  min_odds_for_value: number | null;
}

export interface CaptureLine {
  market: string;
  selection: string;
  line: number | null;
  odds: number;
  player: string | null;
  bookmaker: string;
  text: string | null;
  label?: string;
  eval?: CaptureEval;
  error?: string;
}

export interface Capture {
  id: number;
  status: CaptureStatus;
  created_at: string | null;
  created_local: string | null;
  match_hint: string | null;
  bookmaker_hint: string | null;
  note: string | null;
  match: { match_id: number; home: string; away: string; competition: Competicion; kickoff_local: string } | null;
  lines: CaptureLine[];
  combos: CaptureCombo | null;
  summary: {
    lines: number;
    evaluated: number;
    errors: number;
    bet: number;
    positive_ev: number;
    best: { label: string | null; odds: number; ev: number; verdict: string } | null;
  };
  ai_notes: string | null;
  verdict: string | null;
  edited: boolean;
  engine: string | null;
  auto_engine: "claude_code" | "api" | null;
  error: string | null;
  duration_s: number | null;
  duplicated: boolean;
}
