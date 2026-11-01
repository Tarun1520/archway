import { useCallback, useEffect, useRef, useState } from 'react'
import { AgentsCorner } from '../components/studio/agents/AgentsCorner'
import { AgentsVisit } from '../components/studio/agents/AgentsVisit'
import { ArchyDock } from '../components/studio/archy/ArchyDock'
import { BackendNotice } from '../components/studio/BackendNotice'
import { BackgroundRipple } from '../components/studio/background/BackgroundRipple'
import { BriefView } from '../components/studio/BriefView'
import { DetailsView } from '../components/studio/DetailsView'
import { VoiceSettings } from '../components/studio/VoiceSettings'
import { SidebarDrawer } from '../components/studio/SidebarDrawer'
import { StageHeadline } from '../components/studio/stage/StageHeadline'
import { StudioStage } from '../components/studio/stage/StudioStage'
import { ArrowRight, StudioButton } from '../components/studio/StudioButton'
import { StudioHeader } from '../components/studio/StudioHeader'
import { StudioSidebar } from '../components/studio/StudioSidebar'
import { stages, studioCopy, studioUi, type StageId, type StudioView } from '../content/studio'
import { useBackendConfig } from '../hooks/useBackendConfig'
import { useGithubLimits } from '../hooks/useGithubLimits'
import { useMessages } from '../hooks/useMessages'
import { useReadiness } from '../hooks/useReadiness'
import { useAnyModelThinking } from '../hooks/useModelThinking'
import { useArchy, type IdeaOutcome, type PendingQuestions } from '../hooks/useArchy'
import { useArchySettings } from '../hooks/useArchySettings'
import { usePrefersReducedMotion } from '../hooks/usePrefersReducedMotion'
import { useOptions } from '../hooks/useOptions'
import { usePlan } from '../hooks/usePlan'
import { useMediaQuery } from '../hooks/useMediaQuery'
import { useProjects } from '../hooks/useProjects'
import { useResearch } from '../hooks/useResearch'
import { useRippleWhile } from '../hooks/useRippleWhile'
import { useRun } from '../hooks/useRun'
import { projectNameFromIdea } from '../lib/pendingIdea'
import { fullText } from '../lib/voice/transcript'
import { judgeIdea } from '../lib/api/client'
import { optionsPhase } from '../lib/options'
import { currentStage } from '../lib/stage'

/** The width at which the sidebar stays open beside the content (Tailwind's `lg`). */
const SIDEBAR_QUERY = '(min-width: 1024px)'
/** Where the browser remembers whether the sidebar was folded. */
const FOLDED_KEY = 'archway.sidebarFolded'

function readFolded(): boolean {
  try {
    return window.localStorage.getItem(FOLDED_KEY) === '1'
  } catch {
    return false // storage blocked (private window): just start open
  }
}

/**
 * The studio: where a project is worked on.
 *
 *   background  a grid of dark squares that ripple when clicked (BackgroundRipple)
 *   nav bar     Archway · the views as pills (Studio, Brief, Research, ...) · New project
 *   sidebar     the open project, its five steps, and every project (folds away)
 *   panel       Studio: one step at a time, as a poster (Idea → Questions →
 *               Brief → Research → Shortlist), only what the step needs.
 *               The other views: the full detail of one part (DetailsView).
 *   agents      the agents, drawn as robots, live: who is working, what they
 *               are doing and what they say to each other.
 *   Archy       the voice agent, under the sidebar: rises from a portal,
 *               listens to the idea and starts the brief when told "yes".
 *
 * The sidebar folds into a slim rail of icons (its top button); the browser
 * remembers that choice. On screens narrower than `lg` it becomes a drawer
 * (the nav bar's menu button). The `studio-theme` class re-maps the shared design tokens
 * (styles/tokens.css), so components reused from before take this look.
 */
export function StudioPage() {
  const [view, setView] = useState<StudioView>('studio')
  const [drawerOpen, setDrawerOpen] = useState(false)
  const [creating, setCreating] = useState(false)
  const [folded, setFolded] = useState(readFolded)
  const config = useBackendConfig()
  const projects = useProjects()
  const chat = useMessages(projects.selectedId)
  const run = useRun(projects.selectedId)
  const readiness = useReadiness(projects.selectedId, chat.messages.length)
  const { research } = useResearch(run.snapshot?.run.id ?? null, run.progress.researchVersion)
  const { options } = useOptions(run.snapshot?.run.id ?? null, run.progress.optionsVersion)
  const { plan, markDone } = usePlan(run.snapshot?.run.id ?? null, run.progress.planVersion)
  const busy = run.working || (run.snapshot?.running ?? false)
  const githubLimits = useGithubLimits(busy)
  const closeDrawer = useCallback(() => setDrawerOpen(false), [])

  // Showing that the studio is WAITING, with ripples through the background grid:
  //   a model is thinking (drafting the brief, re-reading after answers,
  //   writing suggestions)  -> ripples from behind the centre of the headline
  //   the agents are at work -> ripples from the lead robot
  // Each stops the moment the wait is over.
  const modelThinking = useAnyModelThinking()
  const agentsAtWork = (run.snapshot?.running ?? false) || run.team.live
  useRippleWhile(!agentsAtWork && (run.working || modelThinking), ['headline', 'panel'], 1500)
  useRippleWhile(agentsAtWork, ['lead', 'headline', 'panel'], 2000)
  const snapshot = run.snapshot
  const waiting = snapshot?.waiting_for ?? null
  const stage = currentStage(snapshot, research, options, plan)

  // --- Archy, the voice agent ---------------------------------------------------
  const voice = config.state === 'ready' ? config.value.voice : undefined
  const { settings: archySettings, change: changeArchy, reset: resetArchy } = useArchySettings()
  const wide = useMediaQuery(SIDEBAR_QUERY)
  // The project whose brief should start as soon as its spoken idea is saved.
  const [beginFor, setBeginFor] = useState<string | null>(null)
  // A project ARCHY opened only so there is a chat box to type into (removed again if nothing was said).
  const archyProject = useRef<string | null>(null)
  // Questions he has already read out in this visit (so they are not read twice).
  const questioned = useRef(new Set<string>())
  // What is in the chat box right now (ChatPanel reports it): the idea is saved from there.
  const chatDraft = useRef('')
  const atIdeaStep = projects.selected !== null && stage === 'idea' && !busy
  // The agents panel is for following a run; the Voice page needs the whole width for its settings.
  // On the Options step the agents have nothing to do, and the side-by-side comparison needs the width.
  // The agents' arrival and departure. They come onto the stage, each in its own way, when the team first appears
  // (and again after they have left). While options are drafted they work in a huddle; when the options are
  // ready they leave the stage, each in its own way, and only THEN are the options shown.
  const optionsNow = optionsPhase(snapshot, options)
  const [agentsEnter, setAgentsEnter] = useState(true)
  const [agentsLeaving, setAgentsLeaving] = useState(false)
  const previousOptionsPhase = useRef(optionsNow)
  useEffect(() => {
    const before = previousOptionsPhase.current
    previousOptionsPhase.current = optionsNow
    if (before === 'drafting' && (optionsNow === 'choosing' || optionsNow === 'no_recommendation')) setAgentsLeaving(true)
  }, [optionsNow])
  const agentsLeft = useCallback(() => {
    setAgentsLeaving(false)
    setAgentsEnter(true) // when the team is shown again, it comes back on
  }, [])
  // Opening the workspace on a page without the agents panel (the Options step, the Voice settings): the team
  // still comes to say hello, on a free spot of the page, waves, and heads off again (AgentsVisit). Once per visit
  // to the workspace, decided only after the project's state has loaded (so it knows which page this is).
  const [greetingDue, setGreetingDue] = useState(true)
  const agentsEntered = useCallback(() => {
    setAgentsEnter(false)
    setGreetingDue(false) // they arrived in their panel: that was the hello
  }, [])
  const reducedMotion = usePrefersReducedMotion()
  // On the Options step the agents are there only while they draft (and while they leave): the side-by-side
  // comparison needs the width. On the Plan step they are not there at all: the prompts need the width.
  const optionsHideAgents = view === 'studio' && ((stage === 'options' && optionsNow !== 'drafting' && !agentsLeaving) || stage === 'plan')
  // Neither the panel nor the visit appears until the project's state has loaded: before that the page cannot tell
  // which step it is on (it would show the panel for a moment, and spend the team's arrival there).
  const pageKnown = !projects.loading && projects.selected !== null && !run.loading && (snapshot === null || (options !== null && plan !== null))
  const showAgents = pageKnown && view !== 'voice' && !optionsHideAgents
  const teamVisits = greetingDue && pageKnown && !showAgents && !reducedMotion

  /** Makes sure a chat box is open for the spoken words, opening a new project when the current one is past its idea step. */
  const prepareChat = async () => {
    setView('studio')
    setVisiting(null)
    if (atIdeaStep) return
    const project = await projects.create('New project', null)
    if (project) archyProject.current = project.id
  }

  /** What was said, together with anything typed in the box before it. */
  const spokenIdea = (heard: string) => chatDraft.current.trim() || heard

  /** Saves the spoken idea as a message, names a project ARCHY opened after it, and asks for the brief. */
  const submitSpokenIdea = async (heard: string): Promise<IdeaOutcome> => {
    const target = projects.selected
    const idea = spokenIdea(heard)
    if (!target || !(await chat.send(idea))) return 'failed'
    if (archyProject.current === target.id) {
      archyProject.current = null
      void projects.rename(target.id, projectNameFromIdea(idea))
    }
    setBeginFor(target.id)
    return 'added'
  }

  /** Is this enough to draft a brief? Counts what is already said in a project still at its idea step. */
  const judgeSpokenIdea = (heard: string) => {
    const earlier = atIdeaStep ? chat.messages.filter((m) => m.role === 'user').map((m) => m.content) : []
    return judgeIdea([...earlier, spokenIdea(heard)].join(' '))
  }
  /** The idea the open project already has: what "I already told you" is checked against. */
  const savedIdea = () => chat.messages.filter((m) => m.role === 'user').map((m) => m.content).join('\n')

  /** Questions the open project's workflow is waiting on (and that he has not read yet), ready to be read out. */
  const pendingQuestions = (): PendingQuestions | null => {
    const waitingFor = snapshot?.waiting_for
    if (busy || !snapshot || !waitingFor || waitingFor.node !== 'clarify') return null
    const questions = waitingFor.payload.questions ?? []
    const key = `${snapshot.run.id}:${questions.map((q) => q.topic).join(',')}`
    if (questions.length === 0 || questioned.current.has(key)) return null
    return {
      questions,
      allowSkip: waitingFor.payload.allow_continue !== false,
      submit: (answers, continueWithAssumptions) => run.answer(answers, continueWithAssumptions),
      claim: () => {
        questioned.current.add(key)
        setView('studio')
        setVisiting(null) // the form must be on screen: the answers are typed into it
      },
    }
  }

  const archy = useArchy({
    settings: archySettings, prepareChat, judgeIdea: judgeSpokenIdea, onIdea: submitSpokenIdea,
    currentIdea: savedIdea, pendingQuestions,
  })

  // Questions are waiting for answers while he is on (the brief he just started, one the person started, or a
  // project reopened): he reads them aloud and hears the answers, instead of asking for an idea.
  useEffect(() => {
    if (archy.phase === 'off') questioned.current.clear() // a new visit reads them again
    if (archy.phase !== 'listening' && archy.phase !== 'asking' && archy.phase !== 'awaiting' && archy.phase !== 'done') return
    const pending = pendingQuestions()
    if (!pending) return
    pending.claim()
    void archy.askQuestions(pending.questions, pending.allowSkip, pending.submit)
  }, [archy.phase, snapshot, busy]) // eslint-disable-line react-hooks/exhaustive-deps

  // Turned off before anything was said: take back the empty project ARCHY opened.
  useEffect(() => {
    const opened = archyProject.current
    if (archy.phase !== 'leaving' || !opened) return
    archyProject.current = null
    if (projects.selectedId === opened && chat.messages.length === 0 && run.snapshot === null) void projects.remove(opened)
  }, [archy.phase]) // eslint-disable-line react-hooks/exhaustive-deps

  // While he speaks, the background grid ripples from behind him (his anchor follows him around the page).
  useRippleWhile(archy.speaking, ['archy'], 900)

  const toggleFolded = () => {
    if (!folded && archy.phase !== 'off') archy.deactivate() // the folded rail has no room for him
    setFolded(!folded)
    try {
      window.localStorage.setItem(FOLDED_KEY, folded ? '0' : '1')
    } catch {
      // Not remembered this time; the sidebar still folds.
    }
  }

  // Start the brief once the idea is saved and that project is the one on screen
  // (for a new project, its messages load a moment after it is selected).
  const ideaSaved = chat.messages.some((message) => message.role === 'user')
  // Just after switching project, the previous project's run is still on hand
  // for a moment, so only a run that belongs to THIS project counts.
  const runProject = run.snapshot?.run.project_id ?? null
  useEffect(() => {
    if (!beginFor || projects.selectedId !== beginFor || run.loading || busy || !ideaSaved) return
    if (runProject === beginFor) {
      setBeginFor(null) // it has a run already: nothing to start
      return
    }
    if (run.snapshot !== null) return // still the previous project's run: wait for this one to load
    setBeginFor(null)
    void run.begin()
  }, [beginFor, projects.selectedId, run.loading, run.snapshot, runProject, busy, ideaSaved, run])

  // A passed step the user went back to (null = show the current step). It is
  // tied to the project, so switching project returns to that project's
  // current step.
  const [visiting, setVisiting] = useState<{ project: string | null; stage: StageId } | null>(null)
  const position = (id: StageId) => stages.findIndex((s) => s.id === id)
  const shown: StageId =
    visiting && visiting.project === projects.selectedId && position(visiting.stage) < position(stage) ? visiting.stage : stage
  const goToStep = (target: StageId) => {
    setView('studio')
    setVisiting(target === stage ? null : { project: projects.selectedId, stage: target })
    window.scrollTo({ top: 0, behavior: 'smooth' })
  }
  // The brief step shows the editable draft right under the headline.
  const editingBrief = view === 'studio' && shown === 'brief' && snapshot?.brief != null

  // One short status for the header, from real state only.
  let status: string | null = null
  if (snapshot) {
    if (busy) status = studioCopy.runStatusLabels.working
    else if (waiting) status = studioCopy.runStatusLabels[waiting.node]
    else if (snapshot.finished) status = options?.approved ? studioCopy.runStatusLabels.approved : research?.finished ? studioCopy.runStatusLabels.finished : studioCopy.runStatusLabels.confirmed
    else if (run.progress.error) status = studioCopy.runStatusLabels.error
    else status = studioCopy.runStatusLabels.idle
  }
  const canRetry = snapshot !== null && !waiting && !snapshot.finished && !busy

  // "New project" opens the name field in the sidebar (in the drawer on a small screen).
  const startNewProject = () => {
    setCreating(true)
    if (!window.matchMedia(SIDEBAR_QUERY).matches) setDrawerOpen(true)
  }

  // The same sidebar is drawn twice: beside the content on wide screens (it can
  // fold), and in the drawer on small ones (its top button closes the drawer).
  const sidebar = (inDrawer: boolean) => (
    // The sidebar on top, Archy's portal below it (the sidebar gives up the room).
    <div className="flex h-full flex-col gap-8">
      <div className="min-h-0 flex-[0_1_auto]">
    <StudioSidebar
      collapsed={inDrawer ? false : folded}
      onToggle={inDrawer ? closeDrawer : toggleFolded}
      toggleLabel={inDrawer ? studioUi.closeSidebar : folded ? studioUi.openSidebar : studioUi.foldSidebar}
      projects={projects.projects}
      selectedId={projects.selectedId}
      loading={projects.loading}
      stage={projects.selected ? stage : null}
      shown={projects.selected && view === 'studio' ? shown : null}
      creating={creating}
      onCreating={setCreating}
      onStep={(target) => {
        goToStep(target)
        setDrawerOpen(false)
      }}
      onSelect={(id) => {
        projects.select(id)
        setDrawerOpen(false)
      }}
      onCreate={(name) => {
        void projects.create(name, null)
        setView('studio')
        setDrawerOpen(false)
      }}
      onDelete={(projectId) => void projects.remove(projectId)}
    />
      </div>
      <ArchyDock
        archy={archy}
        available={voice?.available ?? false}
        tricks={archySettings.tricks}
        wide={wide}
        inDrawer={inDrawer}
        compact={!inDrawer && folded}
        onExpand={() => {
          if (folded) toggleFolded()
        }}
      />
    </div>
  )

  return (
    <div className="studio-theme relative min-h-dvh">
      <BackgroundRipple />

      <div className="relative z-10 flex min-h-dvh flex-col gap-12 p-12 md:gap-16 md:p-16">
        <div className="sticky top-12 z-30 md:top-16">
          <StudioHeader
            status={status}
            live={busy || run.team.live}
            view={view}
            onView={setView}
            onMenu={() => setDrawerOpen(true)}
            onNewProject={startNewProject}
          />
        </div>

        {config.state === 'unreachable' && <BackendNotice reason={config.reason} />}

        <div className="flex flex-1 items-start gap-16">
          {/* The sidebar, kept open on wide screens. It stays in view while the page scrolls. */}
          <aside
            className={`sticky top-[100px] hidden h-[calc(100dvh-116px)] shrink-0 transition-[width] duration-200 lg:block ${folded ? 'w-[68px]' : 'w-[272px]'}`}
          >
            {sidebar(false)}
          </aside>

          {/* The content panel. It is slightly see-through, so the grid shows faintly behind. */}
          <div data-ripple-anchor="panel" className="min-w-0 flex-1 rounded-card border border-line bg-carbon/60">
            <div className={`px-20 md:px-40 2xl:px-56 ${showAgents ? 'xl:grid xl:grid-cols-[minmax(0,1fr)_520px] xl:items-start xl:gap-48' : ''}`}>
              <main className={`min-w-0 pt-40 md:pt-56 ${editingBrief ? 'pb-16' : 'pb-[200px] xl:pb-72'}`}>
                {projects.problem && config.state !== 'unreachable' && (
                  <p role="alert" className="mb-24 text-[15px] text-chalk">
                    {projects.problem}
                  </p>
                )}

                {!projects.selected && !projects.loading ? (
                  // No project yet: the first poster asks for one.
                  <div className="flex flex-col gap-40">
                    <StageHeadline number={0} headline={studioUi.startHeadline} lead={studioUi.startLead} />
                    <div>
                      <StudioButton onClick={startNewProject}>
                        {studioUi.newProject} <ArrowRight />
                      </StudioButton>
                    </div>
                  </div>
                ) : view === 'studio' ? (
                  <StudioStage
                    stage={shown}
                    current={stage}
                    onGoTo={goToStep}
                    snapshot={snapshot}
                    research={research}
                    options={options}
                    plan={plan}
                    holdOptions={agentsLeaving}
                    feed={run.progress.feed}
                    messages={chat.messages}
                    chatProblem={chat.problem}
                    working={busy}
                    problem={run.problem ?? run.progress.error}
                    canRetry={canRetry}
                    onSend={chat.send}
                    readiness={readiness}
                    voice={{ listening: archy.phase === 'listening', text: fullText(archy.heard), sent: archy.sent }}
                    voiceAnswers={archy.answers}
                    voiceTopic={archy.asking}
                    onDraft={(draft) => {
                      chatDraft.current = draft
                    }}
                    onBegin={() => void run.begin()}
                    onRetry={() => void run.retry()}
                    onAnswer={(answers, skip) => void run.answer(answers, skip)}
                    onApprove={() => void run.approve()}
                    onDetails={() => setView('research')}
                    onStartOptions={() => void run.beginOptions()}
                    onChoose={(optionId) => void run.choose(optionId)}
                    onRevise={(optionId, request) => void run.revise(optionId, request)}
                    onApproveOption={() => void run.approveSelected()}
                    onChangeAtApproval={(request) => void run.changeAtApproval(request)}
                    onChangeApproved={(optionId, request) => void run.changeApproved(optionId, request)}
                    onStartPlan={() => void run.beginPlan()}
                    onMarkPromptDone={(path, done) => void markDone(path, done)}
                  />
                ) : view === 'voice' ? (
                  <VoiceSettings
                    settings={archySettings}
                    onChange={changeArchy}
                    onReset={resetArchy}
                    available={voice?.available ?? false}
                  />
                ) : (
                  <DetailsView
                    tab={view}
                    snapshot={snapshot}
                    research={research}
                    feed={run.progress.feed}
                    config={config.state === 'ready' ? config.value : null}
                    githubLimits={githubLimits}
                    working={busy}
                    onApprove={() => void run.approve()}
                    onSaveAndApprove={(edit) => void run.saveEditAndApprove(edit)}
                  />
                )}
              </main>

              {teamVisits && <AgentsVisit onDone={() => setGreetingDue(false)} />}
              {showAgents && (
                <div className="xl:pt-56">
                  <AgentsCorner team={run.team} entrance={agentsEnter} onEntered={agentsEntered} leaving={agentsLeaving} onLeft={agentsLeft} />
                </div>
              )}
            </div>

            {/* The brief draft, editable, across the whole panel from left to right: the
                editors and their AI suggestions need the room, so it sits right
                below the headline rather than inside the narrow column. */}
            {editingBrief && snapshot?.brief && (
              <section
                id="brief-editor"
                aria-label={studioUi.review}
                className="px-8 pb-[200px] md:px-24 xl:pb-48"
              >
                <BriefView
                  key={snapshot.brief.version}
                  brief={snapshot.brief}
                  runId={snapshot.run.id}
                  canDecide={waiting?.node === 'confirm_brief'}
                  working={busy}
                  onApprove={() => void run.approve()}
                  onSaveAndApprove={(edit) => void run.saveEditAndApprove(edit)}
                />
              </section>
            )}
          </div>
        </div>
      </div>

      <SidebarDrawer open={drawerOpen} onClose={closeDrawer}>
        {sidebar(true)}
      </SidebarDrawer>
    </div>
  )
}
