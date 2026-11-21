export interface Party { id: string; name: string; country: string; legal_form?: string }
export interface Evidence { id: string; title: string; text: string; [key: string]: unknown }
export interface DividendCase {
  id: string; title: string; summary: string; category: string; split: string; question: string;
  gross_amount_cents: number; payment_date: string; knowledge_date: string;
  payer: Party; recipient: Party; facts: Record<string, unknown>; documents: Evidence[];
  source_ids: string[]; review_status: string;
}
export interface Source {
  id: string; title: string; url: string; locator: string; text: string;
  retrieved_at: string; sha256: string; [key: string]: unknown;
}
export interface Model { id: string; name: string; configured: boolean; provider: string }
export type HarnessId = 'direct' | 'crewai';
export interface Harness { id: HarnessId; name: string; available: boolean; description: string }
export interface Configuration { id: string; name: string; description: string }
export interface TaxAnswer {
  status: string; relief_eligibility: string; relief_route: string | null;
  withholding_tax_cents: number | null; solidarity_surcharge_cents: number | null;
  total_withholding_cents: number | null; net_payment_cents: number | null;
  refund_status: string; refund_amount_cents: number | null; missing_facts: string[];
  source_ids: string[]; evidence_ids: string[]; reasoning: string;
  [key: string]: unknown;
}
export interface Trial {
  id: string; case_id: string; model_id: string; configuration: string; repetition: number;
  status: string; answer: TaxAnswer | null; error: string | null; passed: boolean;
  grading: Record<string, unknown>; metrics: Record<string, number | null>; trace: unknown[];
}
export interface Summary {
  model_id: string; configuration: string; trials: number; passed: number; failed: number;
  errors?: number; incorrect?: number; cancelled?: number;
  pass_rate: number; avg_wall_time_ms: number | null; avg_input_tokens: number | null;
  avg_output_tokens: number | null; avg_total_tokens: number | null;
}
export interface Run {
  id: string; status: string; created_at: string; updated_at: string; completed_trials: number;
  total_trials: number; request: { case_ids?: string[]; model_ids?: string[]; configurations?: string[]; harness?: HarnessId };
  manifest: Record<string, unknown>; trials: Trial[]; summary: Summary[];
  error?: string | null; cancellation_requested?: boolean;
  active_trial?: {
    case_id: string; model_id: string; configuration: string; repetition: number;
    status: string; usage_complete?: boolean; trace?: unknown[];
    metrics?: Record<string, number | null>;
  } | null;
}
export interface RunRequest {
  case_ids: string[]; model_ids: string[]; configurations: string[]; repetitions: number; max_steps: number; harness: HarnessId;
}
export interface Health { status: string; typedb: Record<string, unknown>; legal_review: string }
export interface Budget {
  limit_eur: number; spent_eur: number; reserved_eur: number;
  committed_eur: number; remaining_eur: number; blocked: boolean;
}
