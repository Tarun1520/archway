/**
 * The one place the frontend talks to the backend.
 *
 * Every function here calls a URL that starts with `/api`. While developing,
 * Vite forwards those requests to the backend on port 8000 (see the `proxy`
 * setting in vite.config.ts), so no backend address is written in the code.
 *
 * SECURITY NOTE: the frontend never holds an API key. Keys live only in
 * backend/.env. The backend's /api/config endpoint returns modes and limits,
 * never secrets.
 */
import type {
  BriefEdit, BriefSuggestions, GithubLimits, Me, Message, OptionsSnapshot, PlanSnapshot, Project, UserChange, UserUsage, PublicConfig, Readiness, ResearchSnapshot, Run, RunSnapshot, Topic,
} from './types'

/** An error from the backend, with the HTTP status code and its message. */
export class ApiError extends Error {
  readonly status: number

  constructor(status: number, message: string) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

/** Sent on `window` when the backend says the session is no longer valid (any 401 outside the sign-in calls). */
export const SIGNED_OUT_EVENT = 'archway:signed-out'

/** Sends one request and returns the parsed JSON answer. */
async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`/api${path}`, {
    ...init,
    headers: { 'Content-Type': 'application/json', ...init?.headers },
  })

  if (response.status === 401 && !path.startsWith('/auth/')) {
    // The session ended (signed out elsewhere, expired, or blocked): tell the app, which shows the sign-in page.
    window.dispatchEvent(new Event(SIGNED_OUT_EVENT))
  }

  if (!response.ok) {
    // The backend explains errors as {"detail": "..."}. Fall back to the
    // status text if the body is not JSON (for example when the backend is off
    // and the dev server answers instead).
    let detail = response.statusText
    try {
      const body = (await response.json()) as { detail?: unknown }
      if (typeof body.detail === 'string') detail = body.detail
    } catch {
      // Not JSON: keep the status text.
    }
    throw new ApiError(response.status, detail)
  }

  // 204 means "done, nothing to send back".
  if (response.status === 204) return undefined as T
  return (await response.json()) as T
}

export function getConfig(): Promise<PublicConfig> {
  return request('/config')
}

/** GitHub's real, current allowance (read from GitHub; reading it costs nothing). */
export function getGithubLimits(): Promise<GithubLimits> {
  return request('/github/limits')
}

export function listProjects(): Promise<Project[]> {
  return request('/projects')
}

export function createProject(name: string, idea: string | null): Promise<Project> {
  return request('/projects', { method: 'POST', body: JSON.stringify({ name, idea }) })
}

/** Deletes a project and everything that belongs to it. This cannot be undone. */
export function deleteProject(projectId: string): Promise<void> {
  return request(`/projects/${projectId}`, { method: 'DELETE' })
}

export function listMessages(projectId: string): Promise<Message[]> {
  return request(`/projects/${projectId}/messages`)
}

/** Is the description enough to draft a brief? (Asked after each saved message.) */
export function getReadiness(projectId: string): Promise<Readiness> {
  return request(`/projects/${projectId}/readiness`)
}

/** The same rule on text that is not saved yet (what Archy just heard). */
export function checkIdeaText(texts: string[]): Promise<Readiness> {
  return request('/readiness', { method: 'POST', body: JSON.stringify({ texts }) })
}

export function addMessage(projectId: string, content: string): Promise<Message> {
  return request(`/projects/${projectId}/messages`, {
    method: 'POST',
    body: JSON.stringify({ role: 'user', content }),
  })
}

// --- Phase 2: runs and the workflow ------------------------------------------

export function listRuns(projectId: string): Promise<Run[]> {
  return request(`/projects/${projectId}/runs`)
}

export function createRun(projectId: string): Promise<Run> {
  return request(`/projects/${projectId}/runs`, { method: 'POST' })
}

export function getRunState(runId: string): Promise<RunSnapshot> {
  return request(`/runs/${runId}/state`)
}

/** Starts the workflow. Resolves when it pauses for the user (or stops). */
export function startRun(runId: string): Promise<RunSnapshot> {
  return request(`/runs/${runId}/start`, { method: 'POST' })
}

export function answerClarify(
  runId: string,
  answers: Partial<Record<Topic, string>>,
  continueWithAssumptions: boolean,
): Promise<RunSnapshot> {
  return request(`/runs/${runId}/clarify`, {
    method: 'POST',
    body: JSON.stringify({ answers, continue_with_assumptions: continueWithAssumptions }),
  })
}

/** Asks for AI suggestions for the newest draft brief. Repeats return the saved ones. */
export function getSuggestions(runId: string, retryStandard = false): Promise<BriefSuggestions> {
  const query = retryStandard ? '?retry_standard=true' : ''
  return request(`/runs/${runId}/suggestions${query}`, { method: 'POST' })
}

export function approveBrief(runId: string): Promise<RunSnapshot> {
  return request(`/runs/${runId}/confirm`, { method: 'POST', body: JSON.stringify({ action: 'approve' }) })
}

export function editBrief(runId: string, edit: BriefEdit): Promise<RunSnapshot> {
  return request(`/runs/${runId}/confirm`, { method: 'POST', body: JSON.stringify({ action: 'edit', edit }) })
}

/** What the research stage found for a run: plan, repositories, evidence and notes. */
export function getResearch(runId: string): Promise<ResearchSnapshot> {
  return request(`/runs/${runId}/research`)
}

// --- Architecture options (Phase 5) ---------------------------------------------------

export function getOptions(runId: string): Promise<OptionsSnapshot> {
  return request(`/runs/${runId}/options`)
}

/** Asks for architecture options after the shortlist. Drafting takes a while: it returns at once and progress arrives as events. */
export function startOptions(runId: string): Promise<RunSnapshot> {
  return request(`/runs/${runId}/options/start`, { method: 'POST' })
}

export function chooseOption(runId: string, optionId: string): Promise<RunSnapshot> {
  return request(`/runs/${runId}/options/select`, { method: 'POST', body: JSON.stringify({ action: 'select', option_id: optionId }) })
}

/** A change to one option: it becomes that option's next version. With nothing on offer, the request guides a fresh draft. */
export function reviseOption(runId: string, optionId: string | null, requestText: string): Promise<RunSnapshot> {
  return request(`/runs/${runId}/options/select`, {
    method: 'POST',
    body: JSON.stringify({ action: 'revise', option_id: optionId, request: requestText }),
  })
}

export function approveOption(runId: string): Promise<RunSnapshot> {
  return request(`/runs/${runId}/options/approve`, { method: 'POST', body: JSON.stringify({ action: 'approve' }) })
}

export function changeOptionAtApproval(runId: string, requestText: string): Promise<RunSnapshot> {
  return request(`/runs/${runId}/options/approve`, { method: 'POST', body: JSON.stringify({ action: 'change', request: requestText }) })
}

/** A change to the APPROVED option after the fact: the next version is drafted, and approval does not carry over. */
export function changeApprovedOption(runId: string, optionId: string, requestText: string): Promise<RunSnapshot> {
  return request(`/runs/${runId}/options/change`, { method: 'POST', body: JSON.stringify({ option_id: optionId, request: requestText }) })
}

// --- Archy (voice) -------------------------------------------------------------------

/** One voice Archy can speak with (backend/app/voice/base.py: VoiceInfo). */
export interface VoiceOption {
  id: string
  name: string
  accent: string
  age: string
  gender: 'feminine' | 'masculine'
  tags: string[]
}

/** A one-time pass for the listening WebSocket, and where to open it ("" = this page's own address). */
export interface VoicePass {
  voice_pass: string
  socket_url: string
}

export function getVoicePass(): Promise<VoicePass> {
  return request('/voice/pass', { method: 'POST' })
}

export function listVoices(): Promise<VoiceOption[]> {
  return request('/voice/voices')
}

/** Gives a project a new name. */
export function renameProject(projectId: string, name: string): Promise<Project> {
  return request(`/projects/${projectId}`, { method: 'PATCH', body: JSON.stringify({ name }) })
}


/** What ARCHY heard: the person's idea, or conversation (with a reply to speak when asked for). */
export interface Understood {
  kind: 'idea' | 'chat'
  reply: string
}

export function understandSpeech(text: string, ideaSoFar: string, wantReply: boolean): Promise<Understood> {
  return request('/voice/understand', { method: 'POST', body: JSON.stringify({ text, idea_so_far: ideaSoFar, want_reply: wantReply }) })
}

/** Is the idea enough to draft a brief? When not, `missing` is one short question for what is missing. */
export interface Judged {
  enough: boolean
  missing: string
}

export function judgeIdea(idea: string): Promise<Judged> {
  return request('/voice/judge', { method: 'POST', body: JSON.stringify({ idea }) })
}

/** A dictated idea, written once and clearly (nothing added, nothing lost). */
export async function tidyIdea(text: string): Promise<string> {
  const reply = await request<{ text: string }>('/voice/tidy', { method: 'POST', body: JSON.stringify({ text }) })
  return reply.text
}

/** What a spoken answer to one of the workflow's questions means. */
export interface SpokenAnswer {
  kind: 'answer' | 'already_told' | 'skip' | 'chat' | 'unclear'
  /** Clean answers, each for the topic of the question it answers (it may be a different question from the one asked). */
  answers: { topic: string; answer: string }[]
  /** Something for ARCHY to say, or ''. */
  reply: string
}

export function interpretAnswer(questions: { topic: string; question: string }[], current: string, idea: string, said: string): Promise<SpokenAnswer> {
  return request('/voice/answer', { method: 'POST', body: JSON.stringify({ questions, current, idea, said }) })
}

// --- The build plan (Phase 6) ----------------------------------------------------------

export function getPlan(runId: string): Promise<PlanSnapshot> {
  return request(`/runs/${runId}/plan`)
}

/** Asks for the roadmap and prompt pack for the approved option version. Returns at once; progress arrives as events. */
export function startPlan(runId: string): Promise<RunSnapshot> {
  return request(`/runs/${runId}/plan/start`, { method: 'POST' })
}

/** Marks one prompt of the plan as done (or not done). */
export function completePrompt(runId: string, path: string, done: boolean): Promise<PlanSnapshot> {
  return request(`/runs/${runId}/plan/prompts/complete`, { method: 'POST', body: JSON.stringify({ path, done }) })
}

/** Where a download of the plan lives: the pack as a zip, the plan as JSON, or as one Markdown document. */
export function planExportUrl(runId: string, format: 'zip' | 'json' | 'md'): string {
  return `/api/runs/${runId}/plan/export.${format}`
}

// --- Accounts ---------------------------------------------------------------------------

/** The signed-in account, or an ApiError with status 401 when nobody is signed in. */
export function getMe(): Promise<Me> {
  return request('/auth/me')
}

export function signIn(email: string, password: string): Promise<Me> {
  return request('/auth/login', { method: 'POST', body: JSON.stringify({ email, password }) })
}

export function signUp(email: string, password: string, name: string | null): Promise<Me> {
  return request('/auth/signup', { method: 'POST', body: JSON.stringify({ email, password, name }) })
}

/** Emails a reset link if the email has an account (the answer is the same either way). */
export function requestPasswordReset(email: string): Promise<void> {
  return request('/auth/forgot', { method: 'POST', body: JSON.stringify({ email }) })
}

/** Sets a new password with the token from an emailed link. */
export function resetPassword(token: string, password: string): Promise<void> {
  return request('/auth/reset', { method: 'POST', body: JSON.stringify({ token, password }) })
}

export async function signOut(): Promise<void> {
  await fetch('/api/auth/logout', { method: 'POST' })
}

// --- Admin ------------------------------------------------------------------------------

/** Every account with its live usage this month (admins only). */
export function listUsers(): Promise<UserUsage[]> {
  return request('/admin/users')
}

/** Changes one account: its monthly token quota (0 = no limit), blocked or active, admin or not. */
export function changeUser(userId: string, change: UserChange): Promise<UserUsage> {
  return request(`/admin/users/${userId}`, { method: 'PATCH', body: JSON.stringify(change) })
}
