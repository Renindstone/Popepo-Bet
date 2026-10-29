// Formas de las respuestas de la API FastAPI (src/apuestas/api/app.py y services/queries.py)

export type Competicion = "EPL" | "BUN" | "LAL" | "SA" | "L1" | "POR" | "BEL" | "UCL" | string;

export interface MatchSummary {
  alerts?: Alert[];
  match_id: number;
  competition: Competicion;
  kickoff_local: string; // "lun 19/10 14:00" (hora de Lima)
  home: string;
  away: string;
  home_id?: number;
  away_id?: number;
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
  alerts?: Alert[];
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
  alerts?: Alert[];
  pick_id?: number;
  match_id?: number;
  match: string;
  home_id?: number;
  away_id?: number;
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
  alerts?: Alert[];
  match_id: number;
  competition: Competicion;
  kickoff_local: string; // "14:00"
  home: string;
  away: string;
  home_id?: number;
  away_id?: number;
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
  prob?: number;
  confidence?: number;
  status: string;
  result: string | null;
  qualifies?: boolean;
  is_pick_of_day?: boolean;
  clv?: number | null;
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
  alerts?: Alert[];
  match_id: number;
  competition: string;
  kickoff_utc: string;
  kickoff_local: string; // "2026-10-20 14:00"
  home: string;
  away: string;
  home_id?: number;
  away_id?: number;
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
  /** CLV medio de las liquidadas que tienen referencia (`with_clv`) */
  avg_clv: number | null;
  with_clv: number;
}

/** De dónde sale la cuota justa (sin margen) del CLV: el cierre de una casa o su último precio antes del partido */
export interface ClvRef {
  book: string;
  kind: "closing" | "live";
  minutes_before: number;
}

/** Una de las que pasaron el corte de valor, probabilidad y confianza (incluye la apuesta del día) */
export interface QualifiedPick {
  pick_id: number;
  date: string;
  match_id: number;
  kickoff_local: string;
  match: string;
  market: string;
  selection: string;
  line: number | null;
  bookmaker: string;
  odds: number;
  prob: number;
  ev: number;
  confidence: number;
  is_pick_of_day: boolean;
  status: string;
  result: string | null;
  clv: number | null;
  closing_odds: number | null;
  clv_ref: ClvRef | null;
  /** Por qué una liquidada no tiene CLV */
  clv_note: string | null;
  profit_units: number | null;
}

export interface QualifiedPicks {
  record: PickRecord;
  picks: QualifiedPick[];
}

export interface PickHistory {
  picks: number;
  profit_units: number;
  roi: number | null;
  hit_rate: number | null;
  avg_clv: number | null;
  last: {
    pick_id: number;
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

/** «Por qué falló» una apuesta del día perdida (GET /picks/{id}/failure) */
export interface FailureReport {
  pick_id: number;
  match: string;
  score: string;
  result: string;
  has_preview: boolean;
  teams: { team: string; side: "home" | "away"; score: number; items: WeekItem[] }[];
  players: { name: string; team: string; score: number; items: WeekItem[] }[];
  flagged: { team: string; kind: "racha" | "baja"; reason: RadarTeam["reason"]; figures_played: string[] }[];
  note: AiNote | null;
}

// --------------------------------------------------------------------------- resumen de la semana (GET /week)

/** Un dato de un partido frente a lo esperado: suma de −1 a +1 (0 = lo esperado) */
export interface WeekItem {
  item: "result" | "goals" | "corners" | "shots" | "shots_on_target" | "assists" | "conceded";
  label: string;
  actual: number | string;
  expected: number;
  line: number | null;
  p_over: number | null;
  source: "casa" | "modelo";
  book: string | null;
  kind: string | null;
  score: number;
}

export interface WeekMatch {
  match_id: number;
  label: string;
  kickoff_local: string;
  stage?: string | null;
  minutes?: number | null;
  score: number;
  items: WeekItem[];
}

export interface WeekTeam {
  team_id: number;
  name: string;
  competition: string;
  score: number;
  mean: number;
  n_matches: number;
  matches?: WeekMatch[];
}

export interface WeekPlayer {
  player_id: number;
  name: string;
  position: string | null;
  team_id: number;
  team: string;
  minutes: number;
  score: number;
  mean: number;
  n_matches: number;
  matches?: WeekMatch[];
}

export interface WeekRecap {
  period: "semana" | "mes";
  weeks: number;
  available: true;
  week_start: string;
  week_end: string;
  status: "en_curso" | "cerrada";
  note: string;
  history_since: string | null;
  coverage: {
    played: number;
    with_prediction: number;
    without_prediction: number;
    stale: number;
    pending_stats: number;
    team_matches: number;
    scheduled: number;
  };
  team_of_week: WeekTeam | null;
  player_of_week: WeekPlayer | null;
  eleven: { formation: string; slots: { line: "GK" | "DF" | "MF" | "FW"; player: WeekPlayer | null }[] };
  teams: WeekTeam[];
  players: WeekPlayer[];
}

/** El mes antes de tener 4 semanas completas con la previa guardada */
export interface MonthUnavailable {
  period: "mes";
  available: false;
  available_from: string | null;
  week_start: string;
  week_end: string;
  note: string;
}

export type PeriodRecap = WeekRecap | MonthUnavailable;

// --------------------------------------------------------------------------- radar de Sorpresas (GET /radar)

/** Explicación escrita por Claude (solo si el usuario usa la IA) */
export interface AiNote {
  status: "pendiente" | "trabajando" | "lista" | "error";
  text: string | null;
  sources: { title: string; url: string }[];
  error: string | null;
  updated_at: string | null;
}

export interface NextMatch {
  match_id: number;
  label: string;
  kickoff_local: string; // "sáb 01/11 12:00"
}

export interface RadarFigure {
  player_id: number;
  name: string;
  score: number;
  lineup?: "confirmado" | "probable" | "sin_once" | null;
}

export interface RadarTeam {
  team_id: number;
  name: string;
  competition: string;
  kind: "racha" | "baja";
  score: number;
  n_matches: number;
  reason: { type: "batacazo" | "pinchazo" | "suma"; match_id: number; label: string; date: string; p_win: number | null };
  figures: RadarFigure[];
  matches?: { match_id: number; label: string; kickoff_local: string; score: number }[];
  next_matches: NextMatch[];
  note?: AiNote | null;
}

export interface RadarPlayer {
  player_id: number;
  name: string;
  team_id: number;
  team: string;
  score: number;
  minutes: number;
  n_matches: number;
  best: { match_id: number; label: string; items: WeekItem[] };
  next_matches: NextMatch[];
  note?: AiNote | null;
}

export interface RadarReport {
  window_start: string;
  window_end: string;
  racha: RadarTeam[];
  baja: RadarTeam[];
  jugadores: RadarPlayer[];
}

/** Aviso de un partido: la ficha del radar de uno de sus equipos, con sus figuras en el once o no */
export type Alert = Omit<RadarTeam, "note"> & { side: "home" | "away"; caveat: string };

/** El usuario de esta clave y sus ajustes (GET /me) */
export interface Me {
  username: string;
  ai_enabled: boolean;
  can_investigate: boolean;
}

/** Sincronización manual de Datos (`GET`/`POST /sync`) */
export interface SyncStatus {
  running: boolean;
  started_at: string | null;
  finished_at: string | null;
  step: string | null;
  done_steps: number;
  total_steps: number;
  error: string | null;
  next_allowed_at: string | null;
}

export interface DataStatus {
  sources: Record<
    string,
    { task: string; finished_at: string | null; status: string; reason?: string | null; last_ok?: string | null }
  >;
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
  /** Apuesta registrada desde esta combinada, si la hay */
  bet_id?: number | null;
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
  /** Apuesta registrada desde esta cuota, si la hay */
  bet_id?: number | null;
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
  auto_engine: "local" | "claude_code" | "api" | null;
  /** Motor para releerla si la lectura no basta ("Leer con Claude"), si hay uno */
  fallback_engine?: "claude_code" | "api" | null;
  error: string | null;
  duration_s: number | null;
  duplicated: boolean;
  /** Importe apostado que Claude vio en la captura (se propone al registrar) */
  stake_seen?: number | null;
}

/** GET /matches/{id}/lineups: alineaciones como en FotMob */
export interface LineupPlayer {
  player_id: number;
  name: string;
  shirt: number | null;
  position: string | null;
  /** Posición en el campo (0-1), vista vertical de FotMob: x a lo ancho, y desde la portería propia */
  x: number | null;
  y: number | null;
  rating: number | null;
}

export interface LineupTeam {
  side: "home" | "away";
  team_id: number;
  team: string;
  formation: string | null;
  coach: string | null;
  starters: LineupPlayer[];
  subs: LineupPlayer[];
  unavailable: { name: string; kind: string; reason: string | null; expected_return: string | null; source: string }[];
}

export interface MatchLineups {
  match_id: number;
  match: string;
  kickoff_local: string;
  status: "predicted" | "confirmed" | null;
  updated_local: string | null;
  teams: LineupTeam[];
}

/** GET /matches/{id}/odds: cuotas guardadas de una casa para el partido, evaluadas */
export interface BookOdd extends BetEval {
  verdict: string;
  min_odds_for_value: number | null;
  label: string;
}

export interface BookOdds {
  match_id: number;
  match: string;
  bookmaker: string;
  captured_local: string | null;
  odds: BookOdd[];
}
