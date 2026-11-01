import { useCallback, useEffect, useMemo, useRef, useState } from 'react'
import {
  answerClarify,
  approveBrief,
  approveOption,
  changeApprovedOption,
  changeOptionAtApproval,
  chooseOption,
  createRun,
  editBrief,
  getRunState,
  listRuns,
  reviseOption,
  startOptions,
  startPlan,
  startRun,
} from '../lib/api/client'
import type { BriefEdit, RunSnapshot, StreamEvent, Topic } from '../lib/api/types'
import { teamFromEvents } from '../lib/agentTeam'
import { progressFromEvents } from '../lib/workflowProgress'

/** Every event name the backend's run stream sends (backend/app/workflow/service.py). */
const EVENT_NAMES = [
  'run_started',
  'run_resumed',
  'node_started',
  'node_finished',
  'node_waiting',
  'activity',
  'usage',
  'brief_updated',
  'capabilities_recorded',
  'components_proposed',
  'eligibility_decided',
  'options_started',
  'options_updated',
  'option_approved',
  'plan_started',
  'plan_updated',
  'team_message',
  'agent_action', // an agent used a tool: drives the robots and their "thinking" line
  'rate_limited',
  'run_error',
  'workflow_finished',
]

/**
 * Everything about the current run of one project: its snapshot, its live
 * events, and the actions the user can take.
 *
 * HOW IT STAYS HONEST AND UP TO DATE
 *   - The SNAPSHOT (brief, what the run is waiting for, usage) is loaded from
 *     the backend, so a page reload or a backend restart shows the true state.
 *   - The EVENTS arrive over a server-sent-events stream. They are saved rows
 *     in the backend's database, so the stream replays from the start and
 *     then continues live. The workflow view is built only from them.
 *   - Each action (start, answer, approve, edit) is one request that returns
 *     when the workflow pauses again, bringing a fresh snapshot.
 */
export function useRun(projectId: string | null) {
  const [snapshot, setSnapshot] = useState<RunSnapshot | null>(null)
  const [events, setEvents] = useState<StreamEvent[]>([])
  const [working, setWorking] = useState(false)
  const [problem, setProblem] = useState<string | null>(null)
  const [loading, setLoading] = useState(false)

  const runId = snapshot?.run.id ?? null

  // --- Load the project's newest run (if it has one) -------------------------
  useEffect(() => {
    setSnapshot(null)
    setEvents([])
    setProblem(null)
    if (projectId === null) return

    let cancelled = false
    setLoading(true)
    const load = async () => {
      try {
        const runs = await listRuns(projectId) // newest first
        const state = runs.length > 0 ? await getRunState(runs[0].id) : null
        if (!cancelled) setSnapshot(state)
      } catch (error) {
        if (!cancelled) setProblem(error instanceof Error ? error.message : 'The run could not be loaded.')
      } finally {
        if (!cancelled) setLoading(false)
      }
    }
    void load()
    return () => {
      cancelled = true
    }
  }, [projectId])

  // --- Listen to the run's events --------------------------------------------
  // True while a snapshot reload is in flight, so a burst of events causes
  // one reload instead of many.
  const refreshing = useRef(false)
  useEffect(() => {
    if (runId === null) return
    setEvents([])

    // EventSource reconnects by itself and tells the server the last event it
    // saw, so nothing is missed and nothing is repeated.
    const stream = new EventSource(`/api/runs/${runId}/events`)
    for (const name of EVENT_NAMES) {
      stream.addEventListener(name, (raw) => {
        const message = raw as MessageEvent<string>
        const data = JSON.parse(message.data) as StreamEvent['data']
        setEvents((current) =>
          // Guard against a repeat if the connection was re-opened.
          current.some((item) => item.id === message.lastEventId)
            ? current
            : [...current, { id: message.lastEventId, name, data }],
        )
        // These events mean the saved picture changed: load it again.
        if (['brief_updated', 'usage', 'node_waiting', 'workflow_finished', 'run_error'].includes(name) && !refreshing.current) {
          refreshing.current = true
          getRunState(runId)
            .then(setSnapshot)
            .catch(() => undefined)
            .finally(() => {
              refreshing.current = false
            })
        }
      })
    }
    return () => stream.close()
  }, [runId])

  // --- Actions ----------------------------------------------------------------
  /** Runs one action, showing "working" while it runs and any problem after. */
  const act = useCallback(async (action: () => Promise<RunSnapshot>) => {
    setWorking(true)
    setProblem(null)
    try {
      setSnapshot(await action())
    } catch (error) {
      setProblem(error instanceof Error ? error.message : 'That did not work.')
    } finally {
      setWorking(false)
    }
  }, [])

  /** Creates a run for the project and starts the workflow. */
  const begin = useCallback(async () => {
    if (projectId === null) return
    await act(async () => {
      const run = await createRun(projectId)
      // Show the new run at once so the event stream opens while it works.
      setSnapshot(await getRunState(run.id))
      return startRun(run.id)
    })
  }, [act, projectId])

  /** Starts again after an error, from the last saved step. */
  const retry = useCallback(async () => {
    if (runId !== null) await act(() => startRun(runId))
  }, [act, runId])

  const answer = useCallback(
    async (answers: Partial<Record<Topic, string>>, continueWithAssumptions: boolean) => {
      if (runId !== null) await act(() => answerClarify(runId, answers, continueWithAssumptions))
    },
    [act, runId],
  )

  const approve = useCallback(async () => {
    if (runId !== null) await act(() => approveBrief(runId))
  }, [act, runId])

  /** Saves the edit as a new version and approves THAT version, in order. */
  const saveEditAndApprove = useCallback(
    async (edit: BriefEdit) => {
      if (runId !== null)
        await act(async () => {
          await editBrief(runId, edit)
          return approveBrief(runId)
        })
    },
    [act, runId],
  )

  const saveEdit = useCallback(
    async (edit: BriefEdit) => {
      if (runId !== null) await act(() => editBrief(runId, edit))
    },
    [act, runId],
  )

  // Work out the workflow view and the feed from the events, only when they change.
  const progress = useMemo(() => progressFromEvents(events), [events])
  // What each agent is doing, for the agents corner (from the same events).
  const team = useMemo(() => teamFromEvents(events), [events])

  // --- Phase 5: options ---------------------------------------------------------------
  const beginOptions = useCallback(async () => {
    if (runId !== null) await act(() => startOptions(runId))
  }, [act, runId])

  const choose = useCallback(
    async (optionId: string) => {
      if (runId !== null) await act(() => chooseOption(runId, optionId))
    },
    [act, runId],
  )

  /** A change to one option (or, with nothing on offer, guidance for a fresh draft): it becomes the next version. */
  const revise = useCallback(
    async (optionId: string | null, request: string) => {
      if (runId !== null) await act(() => reviseOption(runId, optionId, request))
    },
    [act, runId],
  )

  const approveSelected = useCallback(async () => {
    if (runId !== null) await act(() => approveOption(runId))
  }, [act, runId])

  const changeAtApproval = useCallback(
    async (request: string) => {
      if (runId !== null) await act(() => changeOptionAtApproval(runId, request))
    },
    [act, runId],
  )

  const changeApproved = useCallback(
    async (optionId: string, request: string) => {
      if (runId !== null) await act(() => changeApprovedOption(runId, optionId, request))
    },
    [act, runId],
  )

  // --- Phase 6: the build plan ---------------------------------------------------------
  const beginPlan = useCallback(async () => {
    if (runId !== null) await act(() => startPlan(runId))
  }, [act, runId])

  return {
    snapshot, progress, team, working, loading, problem,
    begin, retry, answer, approve, saveEdit, saveEditAndApprove,
    beginOptions, choose, revise, approveSelected, changeAtApproval, changeApproved,
    beginPlan,
  }
}
