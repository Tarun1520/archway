/**
 * The shapes of the data the backend sends and accepts.
 *
 * These mirror the Pydantic models in backend/app/models/ and
 * backend/app/api/config_routes.py. If a backend model changes, change the
 * matching type here.
 *
 * `string | null` means "may be unknown". The UI must show unknown values as
 * unknown, never as an empty or made-up value.
 */

export type ServiceMode = 'live' | 'fixture'

/** What the LIVE / FIXTURE badge is drawn from. Contains no secrets. */
export interface ModeReport {
  jev: ServiceMode
  llm: ServiceMode
  github: ServiceMode
  badge: 'LIVE' | 'FIXTURE'
  fixture_services: string[]
  label: string
}

export interface PublicConfig {
  modes: ModeReport
  caps: {
    max_llm_calls_per_run: number
    max_jev_calls_per_run: number
    /** What one run may use; larger when the backend has a GitHub token. */
    max_github_calls_per_run: number
  }
  llm_provider: string | null
  llm_model: string | null
  /** Archy, the voice agent: whether the backend can listen and talk, and the languages the user may speak. */
  voice?: { available: boolean; languages: Record<string, string> }
  /** Whether "Forgot password?" can email a reset link. */
  password_reset?: boolean
}

export interface Project {
  id: string
  name: string
  idea: string | null
  created_at: string
  updated_at: string
}

export type MessageRole = 'user' | 'assistant' | 'system'

export interface Message {
  id: string
  project_id: string
  role: MessageRole
  content: string
  created_at: string
}

/** One event from the live-progress stream. `demo: true` marks sample data. */
export interface StreamEvent {
  id: string
  name: string
  data: {
    demo?: boolean
    message?: string
    node?: string
    /** On "usage" events: which service was called, and whether it was live or a fixture. */
    service?: string
    mode?: string
    /** On "brief_updated" events: the brief version that was saved. */
    version?: number
    /** On "team_message" events: who wrote to whom. */
    sender?: string
    recipient?: string
    kind?: string
    /** On "agent_action" events: which agent used which tool. */
    agent?: string
    tool?: string
    ok?: boolean
    /** On "agent_action" events: what the call was about (search words, a repository) and how many things it handed in. */
    about?: string | null
    count?: number | null
  }
}

// --- Phase 2: runs, briefs and the workflow ---------------------------------

export interface Requirement {
  id: string
  text: string
}

/** Something Archway assumed. Always shown apart from what the user said. */
export interface Assumption {
  id: string
  text: string
  reason: string | null
}

export interface Constraints {
  budget: string | null
  privacy: string | null
  deployment: string | null
  /** The user's own sentences that read like hard limits, word for word. */
  stated: string[]
}

export interface Conflict {
  description: string
  requirement_ids: string[]
}

export interface ProjectBrief {
  id: string
  version: number
  problem: string
  users: string | null
  must_have: Requirement[]
  nice_to_have: Requirement[]
  stack_preferences: string[]
  constraints: Constraints
  assumptions: Assumption[]
  unknowns: string[]
  conflicts: Conflict[]
  confirmed: boolean
}

/** An item as sent in an edit. Leave `id` out for a brand-new item. */
export interface EditedItem {
  id?: string
  text: string
}

export interface BriefEdit {
  problem: string
  users: string | null
  must_have: EditedItem[]
  nice_to_have: EditedItem[]
  stack_preferences: string[]
  constraints: Constraints
  assumptions: EditedItem[]
  unknowns: string[]
}

/** 'idea' is the question "what would you like to build?", asked when no project was described yet. */
export type Topic = 'idea' | 'meaning' | 'material' | 'deployment' | 'users' | 'sensitive_data' | 'budget' | 'integrations'

export interface ClarifyQuestion {
  topic: Topic
  question: string
  /** One sentence on why the answer matters ("Why we ask"). */
  why?: string | null
}

export interface Run {
  id: string
  project_id: string
  status: string
  brief_confirmed: boolean
  jev_mode: ServiceMode
  llm_mode: ServiceMode
  github_mode: ServiceMode
}

export type WorkflowNode =
  | 'intake'
  | 'clarify'
  | 'confirm_brief'
  | 'research_lead'
  | 'capability_analyst'
  | 'component_scout'
  | 'project_scout'
  | 'reviewer'
  | 'evaluate_candidates'
  | 'draft_options'
  | 'review_options'
  | 'select_or_revise'
  | 'approve_version'
  | 'build_roadmap'
  | 'generate_prompts'
  | 'check_prompts'
  | 'export'

export interface WaitingFor {
  node: 'clarify' | 'confirm_brief' | 'select_or_revise' | 'approve_version'
  /** `allow_continue` is false when the only question is "what would you like to build?". */
  payload: {
    questions?: ClarifyQuestion[]
    brief_version?: number
    allow_continue?: boolean
    /** select_or_revise: the options on offer. */
    presented?: VersionRef[]
    no_recommendation?: boolean
    /** approve_version: the version waiting for approval. */
    option_id?: string
    version?: number
  }
}

export interface UsageCount {
  service: 'llm' | 'jev' | 'github'
  calls: number
  cap: number | null
}

/** Everything needed to redraw a run from nothing (after a reload or a restart). */
/** A question the run asked, with the user's answer (null = skipped, so assumed). */
export interface AskedQuestion {
  topic: string
  question: string
  answer: string | null
}

export interface RunSnapshot {
  run: Run
  waiting_for: WaitingFor | null
  finished: boolean
  /** True while the workflow is working in the background (the research team). */
  running: boolean
  brief: ProjectBrief | null
  brief_versions: number[]
  usage: UsageCount[]
  last_event_id: number
  /** Every question asked, with its answer: for showing the questions step again. */
  asked_questions?: AskedQuestion[]
}

// --- AI suggestions for a draft brief (backend/app/models/suggestions.py) -----

export type AddAs = 'must_have' | 'assumption'
export type ConstraintField = 'budget' | 'privacy' | 'deployment' | 'stated'

export interface Suggestion {
  text: string
  reason: string | null
}

export interface ConstraintSuggestion extends Suggestion {
  field: ConstraintField
}

export interface AnswerSuggestion extends Suggestion {
  add_as: AddAs
  /** True for a generic option added by code because the model gave no answer. */
  standard: boolean
}

export interface UnknownAnswers {
  unknown: string
  answers: AnswerSuggestion[]
}

/** Ideas the model offered. Nothing here is part of the brief until the user adds it. */
export interface BriefSuggestions {
  brief_version: number
  must_have: Suggestion[]
  nice_to_have: Suggestion[]
  stack: Suggestion[]
  constraints: ConstraintSuggestion[]
  assumptions: Suggestion[]
  unknowns: UnknownAnswers[]
  /** Who wrote them: a real model call, or the offline fixture. */
  mode: ServiceMode
  model: string | null
}

// --- Phase 3: the research team (backend/app/models/research.py, evidence.py) ---

export type FetchStatus = 'ok' | 'partial' | 'failed'
export type LicenseStatus = 'detected' | 'unrecognised' | 'none_detected' | 'not_retrieved'
export type AgentName =
  | 'research_lead'
  | 'capability_analyst'
  | 'component_scout'
  | 'project_scout'
  | 'reviewer'
  | 'relevance_judge'

/** What the TOOLS established about one source. Written by code, never by an agent. */
export interface SourceFacts {
  kind: 'github' | 'pypi' | 'npm'
  reference: string
  url: string
  description: string | null
  license: string | null
  license_status: LicenseStatus
  archived: boolean | null
  stars: number | null
  /** Registry packages only: downloads in the last month. Null when not known. */
  downloads_last_month?: number | null
  last_activity: string | null
  inspected: boolean
  evidence_ids: string[]
  mode: ServiceMode
}

export interface Capability {
  id: string
  name: string
  need: string
  requirement_ids: string[]
  approaches: string[]
  search_hints: string[]
  /** "core": a stage of the product's central job, researched first and deepest. "supporting": around it. */
  priority?: 'core' | 'supporting'
}

/** An open-source building block an agent proposed: its claims, plus the facts. */
export interface ComponentCandidate {
  id: string
  capability_id: string
  name: string
  approach: string | null
  provides: string
  fit_notes: string
  concerns: string[]
  facts: SourceFacts
  proposed_by: AgentName
  /** The blind relevance judge's verdict: 3 direct, 2 partial, 1 reference only. Null when not assessed. */
  fit: number | null
  kind: 'building_block' | 'framework' | 'service' | 'reference_app' | null
  fit_reason: string | null
}

export interface SimilarProject {
  name: string
  why_similar: string
  worth_learning: string
  facts: SourceFacts
}

export interface ReviewVerdict {
  complete: boolean
  gaps: { capability_id: string; missing: string }[]
  notes: string
  scouting_seen: number
}

/** One message on the team channel: how the agents talk to each other. */
export interface TeamMessage {
  id: string
  sender: AgentName
  recipient: AgentName | 'team'
  kind: 'task' | 'report' | 'review' | 'note'
  content: string
  capability_ids: string[]
  created_at: string
}

/** What was actually retrieved about one repository. */
export interface RepoEvidence {
  repo: string
  url: string
  retrieved_at: string
  description: string | null
  license: string | null
  archived: boolean | null
  last_push: string | null
  stars: number | null
  readme_excerpt: string | null
  fetch_status: FetchStatus
  missing_fields: string[]
  mode: ServiceMode
  from_cache: boolean
  evidence_ids: string[]
  notes: string[]
}

export type EvidenceSourceType = 'repo_metadata' | 'readme' | 'linked_doc' | 'user_url' | 'package_registry'

/** One quoted source that a claim can rest on. */
export interface EvidenceItem {
  id: string
  url: string
  retrieved_at: string
  source_type: EvidenceSourceType
  excerpt: string | null
  excerpt_location: string | null
  content_hash: string | null
  claim_ids: string[]
  extraction_status: FetchStatus
  mode: ServiceMode
  note: string | null
  repo: string | null
}

/** One outside source a run looked in, from the backend's record of what its tools really used. */
export interface SourceUse {
  source: 'github' | 'npm' | 'pypi' | 'hacker_news' | 'stack_overflow' | 'brave' | string
  lookups: number
  results: number
}

export interface ResearchSnapshot {
  capabilities: Capability[]
  components: ComponentCandidate[]
  projects: SimilarProject[]
  review: ReviewVerdict | null
  messages: TeamMessage[]
  repos: RepoEvidence[]
  evidence: EvidenceItem[]
  notes: string[]
  /** Phase 4: one verdict per component, from the deterministic gate. */
  eligibility: EligibilityVerdict[]
  /** Phase 4: one receipt per question asked of the decision model (Jev). */
  receipts: DecisionReceipt[]
  /** Where this run looked. Missing or empty for runs from before the backend recorded it. */
  sources?: SourceUse[]
  finished: boolean
  mode: ServiceMode
}

export type EligibilityStatus = 'eligible' | 'review_required' | 'unresolved' | 'excluded'

export interface EligibilityVerdict {
  component_id: string
  status: EligibilityStatus
  reasons: string[]
  /** What decided it: the plain rules, or the decision model's answer (older saved verdicts omit this: rules). */
  decided_by?: 'rules' | 'decision_model'
  policy_version: string
}

export interface DecisionReceipt {
  id: string
  candidate_id: string
  requirement_id: string | null
  question_type: 'requirement_fit' | 'integration_risk' | 'needs_human_review'
  rubric_version: string
  jev_mode: ServiceMode
  jev_model_id: string | null
  reported_confidence: number | null
  /** Null means "not evaluated": the question could not be asked. Never a guess. */
  final_result: string | null
  aggregation_policy: string | null
  needs_review: boolean
}

// --- GitHub allowance (the limit bar) ------------------------------------------

/** One GitHub allowance: how many calls it gives, how many are left, and when it refills. */
export interface GithubLimitMeter {
  limit: number
  remaining: number
  seconds_until_reset: number
}

/** GitHub's own account of the allowances research uses. `available` is false in fixture mode. */
export interface GithubLimits {
  available: boolean
  authenticated: boolean
  reason: string | null
  /** Repository details, READMEs and licenses (per hour). */
  core: GithubLimitMeter | null
  /** Repository searches (per minute). */
  search: GithubLimitMeter | null
}

/** Whether a project's description is enough to draft a brief (backend/app/policy/idea_readiness.py). */
export interface Readiness {
  ready: boolean
  /** Why not, in words for the person; null when ready. */
  reason: string | null
}


// --- Architecture options (backend/app/models/option.py, option_flow.py) ------------------------

export type Coverage = 'covered' | 'partial' | 'not_covered' | 'unknown'
export type Rating = 'good' | 'mixed' | 'poor' | 'unknown'
export type Dimension =
  | 'simplicity'
  | 'effort'
  | 'oss_reuse'
  | 'integration_risk'
  | 'maintainability'
  | 'privacy'
  | 'cost_exposure'
  | 'evidence_coverage'

export interface OptionComponent {
  name: string
  responsibility: string
  kind: 'reuse' | 'build'
  repo: string | null
  /** The researched component this reuses, so its eligibility and decisions can be shown beside it. */
  candidate_id: string | null
}

export interface ReviewIssue {
  severity: 'blocking' | 'warning'
  kind: string
  text: string
  /** Plain code found it ("rules") or the reviewing model did. */
  source: 'rules' | 'model'
}

export interface OptionReview {
  passed: boolean
  issues: ReviewIssue[]
  /** False when the model check could not run: the option was judged by the rules alone. */
  llm_checked: boolean
}

export interface ArchitectureOption {
  id: string
  version: number
  brief_version: number
  name: string
  trade_off: string | null
  summary: string
  requirement_coverage: Record<string, Coverage>
  coverage_notes: Record<string, string>
  components: OptionComponent[]
  reused_repos: { repo: string; role: string }[]
  integration_boundaries: string | null
  data_flow: string | null
  storage_model: string | null
  deployment: string | null
  security_privacy: string | null
  testing_approach: string | null
  risks: string[]
  validation_tasks: string[]
  mermaid: string | null
  evidence_ids: string[]
  pros: string[]
  cons: string[]
  choose_if: string | null
  avoid_if: string | null
  comparison: { dimension: Dimension; rating: Rating; note: string }[]
  change_summary: string | null
  review: OptionReview | null
  approved: boolean
}

export interface VersionRef {
  id: string
  version: number
}

export interface OptionsSnapshot {
  requested: boolean
  /** Every version of every option, oldest first. */
  options: ArchitectureOption[]
  /** The newest version of each option that passed review: the only ones to show as choices. */
  presented: VersionRef[]
  selected: VersionRef | null
  /** Approval belongs to ONE version; it is empty once a newer version exists. */
  approved: VersionRef | null
  notes: string[]
  no_recommendation: boolean
}

// --- The build plan (Phase 6): backend/app/models/plan.py ----------------------------------------------------------

export type PlanStage = 'scaffold' | 'data_and_storage' | 'backend_features' | 'integrations' | 'frontend' | 'tests_and_security'

export interface PlanTask {
  id: string
  title: string
  goal: string
  stage: PlanStage
  /** A spike settles an uncertain integration before the work that depends on it. */
  kind: 'build' | 'spike'
  prerequisites: string[]
  scope: string
  out_of_scope: string[]
  likely_files: string[]
  interfaces_to_preserve: string[]
  requirement_ids: string[]
  components: string[]
  evidence_ids: string[]
  acceptance_criteria: string[]
  validation_steps: string[]
  risks: string[]
  validates: string[]
}

export interface PlanDecision {
  id: string
  title: string
  context: string
  decision: string
  rejected: { option: string; why: string }[]
  consequences: string | null
  /** Written by code from the compared options, or by the planning model. */
  source: 'options' | 'model'
}

export interface Roadmap {
  architecture: VersionRef
  brief_version: number
  tasks: PlanTask[]
  decisions: PlanDecision[]
}

export interface RubricCheck {
  criterion: string
  passed: boolean
  detail: string | null
}

export interface PromptFile {
  path: string
  title: string
  kind: 'prompt' | 'context' | 'checklist'
  content: string
  task_ids: string[]
  prerequisites: string[]
  rubric: RubricCheck[]
}

export interface PlanLink {
  requirement_id: string
  requirement: string
  coverage: string
  task_ids: string[]
  components: {
    name: string
    kind: 'reuse' | 'build' | null
    repo: string | null
    candidate_id: string | null
    eligibility: string | null
    decided_by: 'rules' | 'decision_model' | null
    receipt_ids: string[]
    evidence: { id: string; url: string | null }[]
  }[]
}

export interface PlanSnapshot {
  requested: boolean
  /** The option version the plan was built for. */
  built_for: VersionRef | null
  /** The version approved now. When it differs from built_for, the plan is stale. */
  approved: VersionRef | null
  stale: boolean
  roadmap: Roadmap | null
  files: PromptFile[]
  links: PlanLink[]
  /** Every rubric line of every prompt passed (null until checked). */
  passed: boolean | null
  /** "partial": some checks still failed after the one retry. */
  outcome: 'full' | 'partial' | null
  notes: string[]
  /** Prompt paths the person marked as done. */
  completed: string[]
}

// --- Accounts (backend/app/models/user.py, backend/app/api/auth.py) -------------------------------------------------

export interface User {
  id: string
  email: string
  name: string | null
  role: 'user' | 'admin'
  status: 'active' | 'blocked'
  /** Model tokens allowed per calendar month; null = no limit. */
  monthly_token_quota: number | null
  created_at: string
  last_seen_at: string | null
}

/** The signed-in account, and what is left of its quota. */
export interface Me {
  user: User
  tokens_used: number
  tokens_left: number | null
  /** False when the server runs without accounts (one local admin). */
  auth_enabled: boolean
}

/** One account's live usage this month, for the admin dashboard. */
export interface UserUsage {
  user: User
  tokens: number
  llm_calls: number
  decision_calls: number
  github_calls: number
  runs: number
  projects: number
  /** A run of theirs is working right now. */
  working: boolean
  quota_left: number | null
}

export interface UserChange {
  monthly_token_quota?: number
  status?: 'active' | 'blocked'
  role?: 'user' | 'admin'
}
