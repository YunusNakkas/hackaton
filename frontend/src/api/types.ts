export type Role = "employee" | "manager";
export type Difficulty = "easy" | "medium" | "hard";
export type AssignmentStatus = "assigned" | "in_progress" | "completed";
export type PracticeChannel = "message" | "phone";
export type SessionStatus = "active" | "finished";
export type Speaker = "employee" | "customer";
export type TurnStatus = "processing" | "ready" | "error";
export type JobStatus =
  | "queued"
  | "transcribing"
  | "generating"
  | "synthesizing"
  | "evaluating"
  | "ready"
  | "error";
export type JobKind = "opening" | "turn" | "evaluation" | "draft_generation";
export type EvaluationStatus = "pending" | "ready" | "needs_review" | "error";
export type ReviewStatus = "not_required" | "pending" | "reviewed";

export interface Me {
  user: {
    id: string;
    email: string;
    display_name: string;
    role: Role;
    active: boolean;
  };
  organization: { id: string; name: string };
}

export interface Health {
  status: "ok" | "degraded";
  version: string;
  model_service: "up" | "down" | "stub";
  /** Kurulum sesli cevabı destekliyor mu; false ise yalnız yazılı cevap (ör. Windows'ta Ollama). */
  audio_input: boolean;
  tts_provider: string | null;
}

export interface TrainingSummary {
  id: string;
  title: string;
  sector: string;
  language: "tr";
  difficulty: Difficulty;
  summary: string;
  estimated_minutes: number;
  max_turns: number;
}

export interface TrainingDetail extends TrainingSummary {
  customer: { name: string; context: string };
  rubric_dimensions: { id: string; name: string; description: string }[];
  version: {
    scenario_version: string;
    policy_version: string;
    rubric_version: string;
    prompt_version: string;
  };
}

export interface TrainingPage {
  items: TrainingSummary[];
  next_cursor: string | null;
}

export interface Assignment {
  id: string;
  training: TrainingSummary;
  employee_id: string;
  status: AssignmentStatus;
  channel: PracticeChannel;
  assigned_at: string;
  due_at: string | null;
  completed_session_id: string | null;
}

export interface AssignmentPage {
  items: Assignment[];
  next_cursor: string | null;
}

export interface Turn {
  id: string;
  index: number;
  speaker: Speaker;
  status: TurnStatus;
  text: string | null;
  has_audio: boolean;
  duration_ms: number | null;
  created_at: string;
}

export interface Session {
  id: string;
  training: TrainingSummary;
  employee: { id: string; display_name: string };
  assignment_id: string | null;
  channel: PracticeChannel;
  status: SessionStatus;
  evaluation_status: EvaluationStatus | null;
  review_status: ReviewStatus;
  turns: Turn[];
  employee_turn_count: number;
  max_turns: number;
  pending_job_id: string | null;
  started_at: string;
  finished_at: string | null;
}

export interface CreateSessionResponse {
  session: Session;
  opening_job_id: string | null;
}

export interface TurnAccepted {
  job_id: string;
  employee_turn_id: string;
}

export interface FinishAccepted {
  session_id: string;
  evaluation_job_id: string;
}

export interface JobError {
  code: string;
  message: string;
  retryable: boolean;
  failed_stage?: JobStatus | null;
}

export interface Job {
  id: string;
  kind: JobKind;
  status: JobStatus;
  attempt: number;
  poll_after_ms: number;
  result:
    | {
        kind: "turn";
        employee_turn: Turn;
        customer_turn: Turn;
        session_should_end: boolean;
      }
    | { kind: "opening"; customer_turn: Turn }
    | { kind: "evaluation"; session_id: string; evaluation_status: EvaluationStatus }
    | null;
  error: JobError | null;
}

export interface Evidence {
  turn_id: string;
  speaker: Speaker;
  quote: string;
  verified: boolean;
}

export interface DimensionResult {
  dimension_id: string;
  name: string;
  score: number | null;
  max_score: number;
  insufficient_evidence: boolean;
  rationale: string;
  evidence: Evidence[];
  policy_refs: { policy_id: string; title: string; quote: string | null; verified: boolean }[];
}

export interface TotalScore {
  score: number | null;
  max_score: number;
  complete: boolean;
  scored_dimensions: number;
  total_dimensions: number;
}

export interface EvaluationReport {
  dimensions: DimensionResult[];
  total: TotalScore;
  strengths: string[];
  improvements: string[];
  practice_drill: {
    title: string;
    instructions: string;
    focus_dimension_ids: string[];
    example_phrases?: string[];
  } | null;
  flags: string[];
  model_run: { model: string; runtime: string; repaired: boolean };
  effective_total: TotalScore;
  manager_review?: Review | null;
}

export interface EvaluationEnvelope {
  session_id: string;
  status: EvaluationStatus;
  evaluation_job_id: string | null;
  report: EvaluationReport | null;
  error: JobError | null;
}

export interface AdminOverview {
  active_employees: number;
  open_assignments: number;
  completed_assignments: number;
  sessions_pending_review: number;
  sessions_last_7_days: number;
}

export interface Employee {
  id: string;
  email: string;
  display_name: string;
  active: boolean;
  created_at: string;
  open_assignments: number;
  completed_sessions: number;
  last_session_at: string | null;
}

export interface EmployeePage {
  items: Employee[];
  next_cursor: string | null;
}

export interface SessionSummary {
  id: string;
  training: TrainingSummary;
  employee: { id: string; display_name: string };
  status: SessionStatus;
  evaluation_status: EvaluationStatus | null;
  review_status: ReviewStatus;
  total: TotalScore | null;
  employee_turn_count: number;
  started_at: string;
  finished_at: string | null;
}

export interface EmployeeDetail extends Employee {
  assignments: Assignment[];
  recent_sessions: SessionSummary[];
}

export interface SessionPage {
  items: SessionSummary[];
  next_cursor: string | null;
}

export interface DimensionAdjustment {
  dimension_id: string;
  score: number | null;
  original_score?: number | null;
  reason: string;
}

export interface Review {
  id: string;
  reviewer: { id: string; display_name: string };
  decision: "approved" | "adjusted";
  adjustments: DimensionAdjustment[];
  comment: string;
  created_at: string;
}

export interface CreateReviewRequest {
  decision: "approved" | "adjusted";
  adjustments: DimensionAdjustment[];
  comment: string;
}

export interface CreateAssignmentsRequest {
  training_id: string;
  employee_ids: string[];
  channel?: PracticeChannel;
  due_at?: string | null;
}

export interface CreateAssignmentsResponse {
  created: Assignment[];
  skipped_employee_ids: string[];
}

export interface CreateEmployeeRequest {
  email: string;
  display_name: string;
  temporary_password: string;
}

export interface FormPolicy {
  title: string;
  body: string;
}

export interface BusinessRulesForm {
  business_name: string;
  sector: string;
  language: "tr";
  policies: FormPolicy[];
  customer_situations: string[];
  must_do: string[];
  must_not_do: string[];
  escalation_rule?: string | null;
  scenario_count: number;
}

export interface TrainingDraft {
  id: string;
  status: "generating" | "ready" | "error" | "published";
  version: number;
  form: BusinessRulesForm;
  content: {
    scenarios: {
      key: string; title: string; difficulty: Difficulty; summary: string;
      customer: { name: string; context: string; mood: string; hidden_goal: string };
      opening_line: string; success_criteria: string[]; visible_policy_ids: string[]; max_turns: number;
    }[];
    policies: { id: string; title: string; body: string }[];
    rubric: { dimensions: { id: string; name: string; description: string; levels: string[]; weight: number }[] };
  } | null;
  generation_job_id: string | null;
  warnings: string[];
  created_at: string;
  updated_at: string;
  published_training_ids: string[];
}

export interface TrainingDraftPage {
  items: TrainingDraft[];
  next_cursor: string | null;
}
