import { stages, studioCopy, studioUi, type StageId } from '../../../content/studio'
import type { Message, OptionsSnapshot, PlanSnapshot, Readiness, ResearchSnapshot, RunSnapshot, Topic } from '../../../lib/api/types'
import type { FeedLine } from '../../../lib/workflowProgress'
import { ChatPanel, type VoiceInput } from '../ChatPanel'
import { ClarifyForm } from '../ClarifyForm'
import { ArrowRight, StudioButton } from '../StudioButton'
import { Options } from './Options'
import { PastIdea, PastQuestions } from './PastSteps'
import { Plan } from './Plan'
import { ResearchLive } from './ResearchLive'
import { Shortlist } from './Shortlist'
import { StageHeadline } from './StageHeadline'

interface StudioStageProps {
  /** The step on screen: the current one, or a passed one the user went back to. */
  stage: StageId
  /** The step the project is actually on. */
  current: StageId
  onGoTo: (stage: StageId) => void
  snapshot: RunSnapshot | null
  research: ResearchSnapshot | null
  options: OptionsSnapshot | null
  plan: PlanSnapshot | null
  /** The agents are leaving the stage: the options wait for them to go. */
  holdOptions?: boolean
  feed: FeedLine[]
  messages: Message[]
  chatProblem: string | null
  working: boolean
  problem: string | null
  canRetry: boolean
  onSend: (content: string) => Promise<boolean>
  /** Whether the description is enough to draft a brief (null while being checked). */
  readiness: Readiness | null
  /** ARCHY typing the idea into the chat box. */
  voice?: VoiceInput
  /** ARCHY reading the questions: what he has heard so far, and which question he is on. */
  voiceAnswers?: Record<string, string>
  voiceTopic?: string | null
  onDraft?: (draft: string) => void
  onBegin: () => void
  onRetry: () => void
  onAnswer: (answers: Partial<Record<Topic, string>>, skip: boolean) => void
  onApprove: () => void
  onDetails: () => void
  /** Phase 5: ask for options, choose, ask for changes, approve. */
  onStartOptions: () => void
  onChoose: (optionId: string) => void
  onRevise: (optionId: string | null, request: string) => void
  onApproveOption: () => void
  onChangeAtApproval: (request: string) => void
  onChangeApproved: (optionId: string, request: string) => void
  /** Phase 6: ask for the build plan, and mark its prompts as done. */
  onStartPlan: () => void
  onMarkPromptDone: (path: string, done: boolean) => void
}

/**
 * The studio view: one step at a time, as a poster. A numbered rail, one huge
 * headline, a short lead, and only what this step needs.
 *
 * Passed steps can be opened again (from the rail or the sidebar). They are
 * shown read-only, under a bar that leads back to the current step.
 */
export function StudioStage(props: StudioStageProps) {
  const { stage, current, snapshot, research, working, problem, canRetry } = props
  const index = stages.findIndex((s) => s.id === stage)
  const info = stages[index]
  const lookingBack = stage !== current
  const currentInfo = stages.find((s) => s.id === current)

  return (
    <div className="flex flex-col gap-56 md:gap-72">

      {lookingBack && (
        <div className="flex max-w-3xl flex-wrap items-center justify-between gap-12 rounded-card border border-line bg-carbon/80 px-16 py-10">
          <p className="font-code text-label uppercase text-smoke">
            {studioUi.lookingBack} · <span className="text-chalk">{info.label}</span>
          </p>
          <StudioButton variant="ghost" onClick={() => props.onGoTo(current)}>
            {studioUi.backToNow}: {currentInfo?.label} <ArrowRight />
          </StudioButton>
        </div>
      )}

      <StageHeadline number={index + 1} headline={info.headline} lead={lookingBack ? '' : info.lead} />

      {problem && !working && !lookingBack && (
        <div role="alert" className="flex max-w-3xl flex-wrap items-center gap-16 border-l-2 border-vermilion py-8 pl-16">
          <p className="flex-1 text-[16px] text-chalk">
            <span className="mr-8 font-code text-label uppercase text-vermilion">{studioUi.error}</span>
            {problem}
          </p>
          {canRetry && (
            <StudioButton variant="outline" onClick={props.onRetry}>
              {studioUi.retry}
            </StudioButton>
          )}
        </div>
      )}

      {stage === 'idea' && lookingBack && <PastIdea messages={props.messages} />}

      {stage === 'idea' && !lookingBack && (
        <section className="flex max-w-3xl flex-col gap-24">
          <div className="overflow-hidden rounded-card border border-line bg-carbon">
            <ChatPanel messages={props.messages} problem={props.chatProblem} onSend={props.onSend} voice={props.voice} onDraft={props.onDraft} />
          </div>
          <div className="flex flex-wrap items-center gap-24">
            {/* Locked until the description says enough to draft a brief: the reason is shown beside it. */}
            <StudioButton disabled={working || props.messages.length === 0 || props.readiness?.ready !== true} onClick={props.onBegin}>
              {studioUi.createBrief} <ArrowRight />
            </StudioButton>
            <p className={`text-[14px] ${!working && props.readiness?.reason ? 'text-chalk' : 'text-smoke'}`} aria-live="polite">
              {working ? studioCopy.working : props.messages.length > 0 && props.readiness?.reason ? props.readiness.reason : studioCopy.createBriefHint}
            </p>
          </div>
        </section>
      )}

      {stage === 'questions' && lookingBack && <PastQuestions questions={snapshot?.asked_questions ?? []} />}

      {stage === 'questions' && !lookingBack && snapshot?.waiting_for && (
        <div className="max-w-3xl overflow-hidden rounded-card border border-line bg-carbon">
          <ClarifyForm
            questions={snapshot.waiting_for.payload.questions ?? []}
            allowContinue={snapshot.waiting_for.payload.allow_continue !== false}
            working={working}
            onAnswer={props.onAnswer}
            voiceAnswers={props.voiceAnswers}
            voiceTopic={props.voiceTopic}
          />
        </div>
      )}

      {/* The brief step shows the editable draft itself, drawn by the page right below (full width). */}

      {stage === 'research' && <ResearchLive research={research} feed={props.feed} />}

      {stage === 'shortlist' && research && (
        <Shortlist
          research={research}
          onDetails={props.onDetails}
          onStartOptions={lookingBack ? undefined : props.onStartOptions}
          working={working}
          canStartOptions={snapshot?.finished === true && !snapshot.waiting_for}
        />
      )}

      {stage === 'options' && (
        <Options
          run={snapshot}
          options={props.options}
          research={research}
          feed={props.feed}
          working={working}
          holding={props.holdOptions}
          readOnly={lookingBack}
          onChoose={props.onChoose}
          onRevise={props.onRevise}
          onApprove={props.onApproveOption}
          onChangeAtApproval={props.onChangeAtApproval}
          onChangeApproved={props.onChangeApproved}
          plan={props.plan}
          onStartPlan={props.onStartPlan}
          onOpenPlan={() => props.onGoTo('plan')}
        />
      )}

      {stage === 'plan' && (
        <Plan
          run={snapshot}
          plan={props.plan}
          feed={props.feed}
          working={working}
          readOnly={lookingBack}
          onRetry={props.onStartPlan}
          onMarkDone={props.onMarkPromptDone}
        />
      )}
    </div>
  )
}
