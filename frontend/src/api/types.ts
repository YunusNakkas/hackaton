export type Role = "employee" | "manager";
export type Difficulty = "easy" | "medium" | "hard";
export type AssignmentStatus = "assigned" | "in_progress" | "completed";
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
}

export interface EvaluationEnvelope {
  session_id: string;
  status: EvaluationStatus;
  evaluation_job_id: string | null;
  report: EvaluationReport | null;
  error: JobError | null;
}
