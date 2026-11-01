import { useCallback, useEffect, useRef, useState } from 'react'
import { archyHello, archyIntro, archyLines, archyUi, elaborateLine, questionAgainLine, questionLine, questionsIntro, type ArchyAction, type ArchyLine } from '../content/archy'
import { interpretAnswer as interpretAnswerApi, judgeIdea as judgeIdeaApi, tidyIdea as tidyIdeaApi, understandSpeech, type Judged, type SpokenAnswer } from '../lib/api/client'
import type { ArchySettings } from '../lib/voice/archySettings'
import { MicrophoneProblem, startListening, type ListenSession } from '../lib/voice/listenSession'
import { hush, primeSpeaker, say, warm } from '../lib/voice/speaker'
import { NOTHING_HEARD, addResult, fullText, onlyFillers, type Heard } from '../lib/voice/transcript'
import { wantsSkip, yesOrNo } from '../lib/voice/yesNo'

/**
 * Archy, the voice agent: what he is doing, and the conversation he runs.
 *
 *   off ─(click the portal)─> arriving ─> intro ─> listening
 *   listening ─(a pause after some words)─> asking ─> awaiting a yes or no
 *   a too-thin idea ─> he says what is missing and asks for more: NO brief is made
 *   awaiting ─ yes ─> starting (saves the idea, starts the brief) ─> done
 *   done ─(the workflow has questions)─> questions: he reads each one aloud, listens
 *            to the answer (typed into the questions form as it is heard), and sends
 *            the answers, so the brief is drafted from them
 *            ─ no ──> listening again, keeping what was already said
 *            ─ more of the idea ─> added to it, back to listening
 *            ─ unclear ─> asks again (twice at most), then simply waits
 *   any step ─(click the portal or Archy)─> leaving ─> off
 *
 * What the person says while listening is typed into the workspace's chat box
 * (the page reads `heard` and shows it there); Archy's own words are the only
 * thing shown under his portal. How he behaves comes from the settings
 * (lib/voice/archySettings.ts): the language, the voice, how long a pause
 * means "done", whether he asks first, and so on.
 *
 * Each conversation has a number ("generation"). Turning Archy off starts a
 * new number, so any step still waiting from the old conversation sees that
 * it is out of date and quietly stops.
 */

export type ArchyPhase = 'off' | 'arriving' | 'intro' | 'listening' | 'asking' | 'awaiting' | 'starting' | 'questions' | 'done' | 'leaving'
export type IdeaOutcome = 'added' | 'new' | 'failed'

const RISE_MS = 1100
const LEAVE_MS = 900
const HEARD_INTRO_KEY = 'archway.archyIntroHeard'
const ASK_AGAIN_LIMIT = 2
/** A dropped listening line is reconnected this many times before the person is told. */
const MAX_RECONNECTS = 3
/** He listens for English as spoken in India: it also understands other English accents well. */
const LISTEN_LANGUAGE = 'en-IN'
/** A pause this long ends one thing the person said: he may then answer it, if it was conversation. */
const UTTERANCE_PAUSE_MS = 1600
/** How long he waits for the first word of an answer before taking the question as skipped. */
const ANSWER_WAIT_MS = 12000
/** Said while waiting for yes or no: this many words or more is taken as more of the idea. */
const MORE_IDEA_WORDS = 4

export interface ArchyState {
  phase: ArchyPhase
  action: ArchyAction
  /** What Archy is saying (or last said). */
  line: string | null
  /** What the person has said so far (typed into the chat box). */
  heard: Heard
  /** How loud the microphone is, while listening. */
  level: number
  problem: string | null
  /** Counts up each time a spoken idea has been saved, so the chat box can clear itself. */
  sent: number
  /** True while he is saying a line (the studio ripples the background from behind him). */
  speaking: boolean
  /** The answers heard so far to his questions, by topic (typed into the questions form). */
  answers: Record<string, string>
  /** The topic of the question he is asking now. */
  asking: string | null
}

/** A question the workflow asks (backend ClarifyQuestion). */
export interface SpokenQuestion {
  topic: string
  question: string
}

/** Questions the workflow is waiting on right now, ready for him to read out. */
export interface PendingQuestions {
  questions: SpokenQuestion[]
  allowSkip: boolean
  /** Sends the answers on. */
  submit: (answers: Record<string, string>, continueWithAssumptions: boolean) => Promise<void>
  /** Marks them as taken, so they are not read twice. */
  claim: () => void
}

interface Options {
  settings: ArchySettings
  /** Makes sure a project at its idea step is open, so there is a chat box for the words. */
  prepareChat: () => Promise<void>
  /** Is the idea (with anything already in the project) enough to draft a brief? If not, what is missing? */
  judgeIdea?: (idea: string) => Promise<Judged>
  /** Saves the spoken idea and starts the brief. */
  onIdea: (idea: string) => Promise<IdeaOutcome>
  /** The idea as dictated, written once and clearly. */
  tidyIdea?: (text: string) => Promise<string>
  /** What a spoken answer to one of the questions means. */
  interpretAnswer?: (questions: SpokenQuestion[], current: string, idea: string, said: string) => Promise<SpokenAnswer>
  /** The idea the open project already has (so "I already told you" can be checked against it). */
  currentIdea?: () => string
  /** Questions waiting for answers in the open project, if any: he reads those instead of asking for an idea. */
  pendingQuestions?: () => PendingQuestions | null
}

const START: ArchyState = { phase: 'off', action: 'idle', line: null, heard: NOTHING_HEARD, level: 0, problem: null, sent: 0, speaking: false, answers: {}, asking: null }

export function useArchy({
  settings, prepareChat, judgeIdea = (idea) => judgeIdeaApi(idea), onIdea,
  tidyIdea = (text) => tidyIdeaApi(text), interpretAnswer = interpretAnswerApi, currentIdea, pendingQuestions,
}: Options) {
  const [state, setState] = useState<ArchyState>(START)
  const generation = useRef(0)
  const session = useRef<ListenSession | null>(null)
  const silence = useRef<number | null>(null)
  const utterance = useRef<number | null>(null)
  // What he has understood so far. Each thing the person says is decided on (idea or conversation):
  //   committed   the phrases that are the idea (typed into the chat box)
  //   chatBuffer  phrases that were conversation, waiting for him to reply
  //   mode        "idea" once the person is describing something: words are then typed as they arrive
  const committed = useRef<string[]>([])
  const chatBuffer = useRef<string[]>([])
  const chatReplies = useRef<string[]>([]) // his reply to each buffered phrase, made while the person was still speaking
  const verdict = useRef<{ idea: string; result: Promise<Judged> } | null>(null) // "is it enough?", asked ahead of time
  const tidied = useRef<{ raw: string; result: Promise<string> } | null>(null) // the cleaned-up idea, also made ahead of time
  const mode = useRef<'unknown' | 'idea'>('unknown')
  const interim = useRef('')
  const chain = useRef<Promise<void>>(Promise.resolve()) // phrases are decided on one at a time, in order
  // The latest values, for steps that wait a while (they must not use stale ones).
  const latest = useRef({ settings, prepareChat, judgeIdea, onIdea, tidyIdea, interpretAnswer, currentIdea, pendingQuestions })
  latest.current = { settings, prepareChat, judgeIdea, onIdea, tidyIdea, interpretAnswer, currentIdea, pendingQuestions }

  const update = (patch: Partial<ArchyState>) => setState((current) => ({ ...current, ...patch }))
  const current = (gen: number) => gen === generation.current

  const clearSilence = () => {
    if (silence.current !== null) window.clearTimeout(silence.current)
    silence.current = null
    if (utterance.current !== null) window.clearTimeout(utterance.current)
    utterance.current = null
  }

  const ideaText = () => committed.current.join(' ').trim()
  /** Shows the idea so far (and the words being spoken, once he knows they are the idea) in the chat box. */
  const show = () => update({ heard: { finals: [...committed.current], interim: mode.current === 'idea' ? interim.current : '' } })

  const stopListening = async (wait: boolean) => {
    clearSilence()
    const open = session.current
    session.current = null
    if (!open) return
    if (wait) await open.stop()
    else open.cancel()
    update({ level: 0 })
  }

  /** Says one line, with its gesture, in the chosen voice. */
  const speak = async (gen: number, line: ArchyLine, phase: ArchyPhase) => {
    if (!current(gen)) return
    const { settings: s } = latest.current
    // The gesture starts at once; the words (and the ripples) appear when the sound really starts,
    // so what is on screen and what is heard stay together.
    update({ phase, action: line.action, speaking: false })
    await say(line.text, {
      voice: s.voice, speed: s.speed, volume: s.volume, speak: s.speak,
      onStart: () => current(gen) && update({ line: line.text, speaking: true }),
    })
    if (current(gen)) update({ speaking: false })
  }

  /** Starts making the sound of lines he is likely to say soon, so they begin without a wait. */
  const prepare = (lines: string[]) => {
    const { settings: s } = latest.current
    warm(lines, { voice: s.voice, speed: s.speed, speak: s.speak })
  }

  /**
   * The idea so far, cleaned up: restarts and repeated fragments removed, requests to him dropped, nothing
   * added. Made once for each version of the words, and begun at the short pause so it is ready in time.
   * If it cannot be made, the words are used as they are.
   */
  const refine = (): Promise<string> => {
    const raw = ideaText()
    if (tidied.current?.raw === raw) return tidied.current.result
    const result = raw && !onlyFillers(raw) ? latest.current.tidyIdea(raw).catch(() => raw) : Promise.resolve(raw)
    tidied.current = { raw, result }
    return result
  }

  /**
   * Asks "is the idea so far enough for a brief?" - once for each version of the idea. Called at the
   * short pause (so the answer is ready early) and again at the long one (which reuses it).
   */
  const prejudge = (): Promise<Judged> => {
    const idea = ideaText()
    if (verdict.current?.idea === idea) return verdict.current.result
    const result = idea && !onlyFillers(idea) ? latest.current.judgeIdea(idea) : Promise.resolve<Judged>({ enough: false, missing: '' })
    verdict.current = { idea, result }
    // The words he will say next are made ready as soon as the verdict is known.
    result.then((found) => prepare(found.enough ? [] : [elaborateLine(found.missing || null).text])).catch(() => undefined)
    return result
  }

  const micProblem = (error: unknown) =>
    error instanceof MicrophoneProblem
      ? error.message === 'blocked'
        ? archyUi.micBlocked
        : error.message === 'missing'
          ? archyUi.micMissing
          : archyUi.micFailed
      : error instanceof Error
        ? error.message
        : archyUi.micFailed

  /** Opens the microphone; `onWords` receives each result. */
  const openMic = async (gen: number, onWords: (text: string, final: boolean) => void, reconnects = 0): Promise<boolean> => {
    let mine: ListenSession | null = null
    try {
      const opened = await startListening(
        LISTEN_LANGUAGE,
        {
          onWords: (text, final) => current(gen) && onWords(text, final),
          onLevel: (level) => current(gen) && update({ level }),
          onError: (message) => {
            if (!current(gen)) return
            // The line dropped while he was still meant to be listening: quietly connect again (a few times at most).
            if (session.current === mine && reconnects < MAX_RECONNECTS) {
              session.current = null
              void openMic(gen, onWords, reconnects + 1)
              return
            }
            update({ problem: message, level: 0 })
          },
        },
        true, // "um" and "hmm" are kept: they show that every sound is heard
      )
      mine = opened
      if (!current(gen)) {
        opened.cancel()
        return false
      }
      session.current = opened
      if (reconnects > 0) update({ problem: null })
      return true
    } catch (error) {
      if (current(gen)) update({ problem: micProblem(error), action: 'think' })
      return false
    }
  }

  // --- Listening for the idea ---------------------------------------------------
  /**
   * Decides what ONE phrase is: part of the idea, or conversation. Phrases are decided in order.
   * Once the person is describing something, new words are typed straight away and taken back if
   * the phrase turns out to be conversation; before that, nothing is typed until the first
   * phrase is understood as the idea.
   */
  const decidePhrase = (gen: number, phrase: string) => {
    chain.current = chain.current.then(async () => {
      if (!current(gen)) return
      const optimistic = mode.current === 'idea'
      if (optimistic) committed.current.push(phrase)
      show()
      let kind: 'idea' | 'chat' = 'idea' // if he cannot tell, the words are kept: nothing the person said is lost
      let reply = ''
      try {
        const sofar = (optimistic ? committed.current.slice(0, -1) : committed.current).join(' ')
        // His reply is asked for in the same call, so it is ready by the time the person stops talking.
        const understood = await understandSpeech(phrase, sofar, true)
        kind = understood.kind
        reply = understood.reply
      } catch {
        // the words stay
      }
      if (!current(gen)) return
      if (kind === 'idea') {
        mode.current = 'idea'
        if (!optimistic) committed.current.push(phrase)
      } else {
        if (optimistic) committed.current.pop()
        chatBuffer.current.push(phrase)
        chatReplies.current.push(reply)
        if (reply) prepare([reply]) // the voice is made while the pause runs out
        mode.current = committed.current.length > 0 ? 'idea' : 'unknown'
      }
      show()
    })
  }

  /** A short pause: if what was just said was conversation, he answers it. */
  const answerConversation = async (gen: number) => {
    await chain.current
    if (!current(gen)) return
    if (chatBuffer.current.length === 0) {
      prejudge() // a pause after the idea: find out now whether it is enough, and tidy the words, so both are ready at the 4-second mark
      void refine()
      return
    }
    const said = chatBuffer.current.join(' ')
    const ready = chatBuffer.current.length === 1 ? chatReplies.current[0] : ''
    chatBuffer.current = []
    chatReplies.current = []
    let reply = ready
    // He must not hear himself, so listening stops; the reply (if not already made) is asked for at the same time.
    const [, understood] = await Promise.all([
      stopListening(true),
      ready ? Promise.resolve(null) : understandSpeech(said, ideaText(), true).catch(() => null),
    ])
    if (!ready) {
      if (understood?.kind === 'idea') {
        committed.current.push(said) // on a second look it was part of the idea after all
        mode.current = 'idea'
        show()
        reply = ''
      } else {
        reply = understood?.reply || archyLines.generalReply.text
      }
    }
    if (!current(gen)) return
    if (reply) await speak(gen, { action: 'explain', text: reply }, 'listening')
    void listenForIdea(gen, true, true)
  }

  const listenForIdea = async (gen: number, keepWhatWasSaid: boolean, afterReply = false) => {
    if (!current(gen)) return
    if (!keepWhatWasSaid) {
      committed.current = []
      chatBuffer.current = []
      chatReplies.current = []
      verdict.current = null
      tidied.current = null
      mode.current = 'unknown'
      prepare([archyLines.ask.text, archyLines.starting.text, archyLines.keepGoing.text, archyLines.done.text])
    }
    interim.current = ''
    update({ phase: 'listening', action: 'listen', problem: null })
    show()

    const arm = () => {
      clearSilence()
      utterance.current = window.setTimeout(() => void answerConversation(gen), UTTERANCE_PAUSE_MS)
      silence.current = window.setTimeout(() => void ideaFinished(gen), latest.current.settings.pauseSeconds * 1000)
    }
    const opened = await openMic(gen, (text, final) => {
      if (!text.trim()) return // empty results while it hears nothing must not restart the timers
      if (final) {
        interim.current = ''
        decidePhrase(gen, text.trim())
      } else {
        interim.current = text.trim()
        if (mode.current === 'idea') show()
      }
      arm()
    })
    // After he has answered some conversation, a quiet moment with an idea already said is also "I am done".
    if (opened && afterReply && committed.current.length > 0) {
      silence.current = window.setTimeout(() => void ideaFinished(gen), latest.current.settings.pauseSeconds * 1000)
    }
  }

  const ideaFinished = async (gen: number) => {
    if (!current(gen)) return
    await chain.current // every phrase has been decided on
    if (!current(gen) || committed.current.length === 0) return // only conversation so far: nothing to go on with
    prejudge() // already running if the pause was long enough; this reuses it
    void refine()
    await stopListening(true) // collects the last words
    await chain.current
    if (!current(gen)) return
    const idea = ideaText()
    if (onlyFillers(idea)) {
      void listenForIdea(gen, false) // only "um"s so far: keep listening
      return
    }
    update({ action: 'think' })
    // Is it enough to draft a brief, and what do the words say once cleaned up? Both are asked at the same time.
    let found: Judged = { enough: true, missing: '' }
    const [verdictResult, cleaned] = await Promise.allSettled([prejudge(), refine()])
    if (!current(gen)) return
    if (verdictResult.status === 'fulfilled') found = verdictResult.value
    // else: the check could not be made. Carry on; the backend refuses a start that is not ready, and says why.
    if (cleaned.status === 'fulfilled' && cleaned.value.trim() && cleaned.value !== idea && ideaText() === idea) {
      committed.current = [cleaned.value] // the chat box now shows the idea written once, clearly
      show()
    }
    update({ phase: 'asking' })
    if (!found.enough) {
      await speak(gen, elaborateLine(found.missing || null), 'listening')
      void listenForIdea(gen, true)
      return
    }
    await askToContinue(gen, 0) // he always asks first
  }

  // --- Asking "shall I continue to the brief?" ------------------------------------
  const askToContinue = async (gen: number, asked: number) => {
    await speak(gen, asked === 0 ? archyLines.ask : archyLines.askAgain, 'asking')
    if (!current(gen)) return
    update({ phase: 'awaiting', action: 'listen' })
    let asks = asked
    await openMic(gen, (text, final) => {
      if (!final || !text.trim()) return
      const answer = yesOrNo(text)
      if (answer === 'yes') {
        void stopListening(false)
        void createBrief(gen)
      } else if (answer === 'no') {
        void stopListening(false)
        void keepListening(gen)
      } else if (onlyFillers(text)) {
        // A "hmm" is not an answer yet.
      } else if (text.trim().split(/\s+/).length >= MORE_IDEA_WORDS) {
        // Not an answer: more of the idea. Add it and go on listening.
        committed.current.push(text.trim())
        mode.current = 'idea'
        show()
        void stopListening(false)
        void listenForIdea(gen, true)
      } else if (asks < ASK_AGAIN_LIMIT) {
        asks += 1
        void stopListening(false)
        void askToContinue(gen, asks)
      }
      // Asked enough times: he simply waits for a clear yes or no.
    })
  }

  const createBrief = async (gen: number) => {
    await stopListening(false)
    await speak(gen, archyLines.starting, 'starting')
    if (!current(gen)) return
    const outcome = await latest.current.onIdea(ideaText())
    if (!current(gen)) return
    if (outcome === 'failed') {
      await speak(gen, archyLines.failed, 'awaiting')
      return
    }
    committed.current = []
    chatBuffer.current = []
    chatReplies.current = []
    verdict.current = null
    tidied.current = null
    mode.current = 'unknown'
    setState((now) => ({ ...now, heard: NOTHING_HEARD, sent: now.sent + 1 }))
    await speak(gen, archyLines.done, 'done')
    if (current(gen)) update({ action: 'idle' })
  }

  const keepListening = async (gen: number) => {
    await speak(gen, archyLines.keepGoing, 'listening')
    void listenForIdea(gen, true)
  }

  // --- Reading the questions and hearing the answers --------------------------------
  /** Listens for ONE answer, typing it into the form as it is heard. '' = nothing said; null = could not listen. */
  const heardAnswer = async (gen: number, topic: string): Promise<string | null> => {
    let local: Heard = NOTHING_HEARD
    let settle: () => void = () => undefined
    const quiet = new Promise<void>((resolve) => {
      settle = resolve
    })
    let waitTimer = window.setTimeout(settle, ANSWER_WAIT_MS)
    const opened = await openMic(gen, (text, final) => {
      // The service also sends empty results while it hears nothing: those must not restart the pause.
      if (!text.trim()) {
        local = addResult(local, text, final)
        return
      }
      local = addResult(local, text, final)
      const typed = fullText(local)
      setState((now) => ({ ...now, answers: { ...now.answers, [topic]: typed } }))
      window.clearTimeout(waitTimer)
      clearSilence()
      if (!onlyFillers(typed)) {
        // Something was said: a pause now means "that is my answer".
        silence.current = window.setTimeout(settle, latest.current.settings.pauseSeconds * 1000)
      } else {
        waitTimer = window.setTimeout(settle, ANSWER_WAIT_MS)
      }
    })
    if (!opened) {
      window.clearTimeout(waitTimer)
      return null
    }
    await quiet
    window.clearTimeout(waitTimer)
    await stopListening(true) // collects the last words
    return current(gen) ? fullText(local) : null
  }

  /**
   * Reads the workflow's questions aloud, one by one, and listens for each answer.
   *
   * What is said is typed into the questions form as it is heard, then understood (by the model) and
   * replaced by a clean answer. One reply can answer more than one question, so a question already answered
   * is not asked again. "I already told you" is checked against the idea the person gave. A question back to
   * him is answered, and the question is asked again. A short "skip" (or "I do not know") leaves a question
   * unanswered, which becomes an assumption in the brief, when the workflow allows it. At the end he hands the
   * answers to `submit`, which sends them on.
   *
   * It may start while he is doing something else (listening for an idea, say): that conversation is ended.
   */
  const askQuestions = useCallback(
    async (
      questions: SpokenQuestion[],
      allowSkip: boolean,
      submit: (answers: Record<string, string>, continueWithAssumptions: boolean) => Promise<void>,
    ) => {
      if (questions.length === 0) return
      await stopListening(false)
      hush()
      const gen = ++generation.current // whatever he was doing before sees it is out of date and stops
      setState((now) => ({ ...now, answers: {} }))
      await speak(gen, questionsIntro(questions.length), 'questions')

      const given: Record<string, string> = {}
      const type = (topic: string, value: string) => setState((now) => ({ ...now, answers: { ...now.answers, [topic]: value } }))
      const remember = (items: { topic: string; answer: string }[]) => {
        for (const item of items) {
          given[item.topic] = item.answer
          type(item.topic, item.answer)
        }
      }
      const attempts = allowSkip ? 2 : 3
      for (let index = 0; index < questions.length; index++) {
        const { topic, question } = questions[index]
        if (given[topic]) continue // answered while answering another question
        if (!current(gen)) return
        update({ asking: topic })
        let lead: ArchyLine | null = null // what he says before asking again: a reply, or why
        for (let attempt = 0; attempt < attempts; attempt++) {
          if (lead) await speak(gen, lead, 'questions')
          await speak(gen, attempt === 0 ? questionLine(index, questions.length, question) : questionAgainLine(question), 'questions')
          if (!current(gen)) return
          update({ action: 'listen' })
          const text = await heardAnswer(gen, topic)
          if (!current(gen)) return
          if (text === null) {
            update({ asking: null }) // the microphone failed: the problem is shown, and the form can still be typed into
            return
          }
          lead = null
          if (!text.trim() || onlyFillers(text)) {
            type(topic, '')
            if (allowSkip) break // nothing said: left for an assumption
            lead = archyLines.mustAnswer
            continue
          }
          if (allowSkip && wantsSkip(text)) {
            type(topic, '')
            break
          }
          // What did the person mean? (If that cannot be found out, what they said is the answer.)
          let meant: SpokenAnswer
          try {
            meant = await latest.current.interpretAnswer(questions, topic, latest.current.currentIdea?.() ?? '', text)
          } catch {
            meant = { kind: 'answer', answers: [{ topic, answer: text.trim() }], reply: '' }
          }
          if (!current(gen)) return
          remember(meant.answers)
          if (given[topic]) break
          type(topic, '') // the raw words typed while he listened are not an answer: take them out
          if (meant.kind === 'skip') {
            if (allowSkip) break
            lead = archyLines.mustAnswer
          } else {
            lead = { action: 'explain', text: meant.reply || "Sorry, I didn't catch an answer to that." }
          }
        }
        if (!given[topic] && allowSkip) await speak(gen, archyLines.skipped, 'questions')
      }
      update({ asking: null })
      if (!current(gen)) return

      const everyOne = questions.every((q) => given[q.topic])
      if (!everyOne && !allowSkip) {
        await speak(gen, archyLines.questionsStuck, 'done') // the form is left as it is, for the person to finish
        return
      }
      const sending = submit(given, !everyOne)
      await speak(gen, archyLines.questionsDone, 'done')
      await sending
      if (current(gen)) update({ action: 'idle' })
    },
    [], // eslint-disable-line react-hooks/exhaustive-deps
  )

  // --- Coming and going --------------------------------------------------------
  /** Wakes Archy. Must be called from a click: that is what allows sound. */
  const activate = useCallback(() => {
    if (state.phase !== 'off') return
    const gen = ++generation.current
    primeSpeaker()
    committed.current = []
    chatBuffer.current = []
    chatReplies.current = []
    verdict.current = null
    mode.current = 'unknown'
    setState((now) => ({ ...START, sent: now.sent, phase: 'arriving', action: 'rise' }))

    // Which introduction he gives is known now, so its sound is made while he rises out of the portal.
    const introMode = latest.current.settings.intro
    let lines: ArchyLine[] = archyIntro
    let met = false
    try {
      met = Boolean(window.localStorage.getItem(HEARD_INTRO_KEY))
    } catch {
      // storage blocked: just give the full introduction
    }
    if (introMode === 'never') lines = []
    else if (introMode === 'first' && met) lines = archyHello
    // Questions are waiting for answers: he has come to help with those, so no introduction about ideas.
    const questionsWaiting = Boolean(latest.current.pendingQuestions?.())
    if (questionsWaiting) lines = introMode === 'never' ? [] : [archyLines.helloQuestions]
    prepare(lines.map((line) => line.text))

    void (async () => {
      await new Promise((resolve) => window.setTimeout(resolve, RISE_MS))
      for (const line of lines) {
        if (!current(gen)) return
        await speak(gen, line, 'intro')
      }
      if (!current(gen)) return
      const pending = latest.current.pendingQuestions?.() ?? null
      if (pending) {
        pending.claim()
        void askQuestions(pending.questions, pending.allowSkip, pending.submit)
        return
      }
      try {
        window.localStorage.setItem(HEARD_INTRO_KEY, '1')
      } catch {
        // not remembered; the full introduction plays again next time
      }
      await latest.current.prepareChat() // the chat box the words will be typed into
      void listenForIdea(gen, false)
    })()
  }, [state.phase]) // eslint-disable-line react-hooks/exhaustive-deps

  /** Puts Archy away, stopping whatever he was doing. */
  const deactivate = useCallback(() => {
    generation.current += 1
    hush()
    void stopListening(false)
    update({ phase: 'leaving', action: 'idle', level: 0 })
    const gen = generation.current
    window.setTimeout(() => {
      if (current(gen)) setState((now) => ({ ...START, sent: now.sent }))
    }, LEAVE_MS)
  }, []) // eslint-disable-line react-hooks/exhaustive-deps

  // Leaving the page turns Archy off cleanly (microphone light off, voice silent).
  useEffect(
    () => () => {
      generation.current += 1
      hush()
      session.current?.cancel()
      clearSilence()
    },
    [],
  )

  return { ...state, activate, deactivate, askQuestions }
}

export type Archy = ReturnType<typeof useArchy>
