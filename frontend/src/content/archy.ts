/**
 * Everything Archy, the voice agent, says and shows.
 *
 * Each spoken line comes with an ACTION: the gesture the robot makes while
 * saying it (components/studio/archy/ArchyBot.tsx draws them). Archy speaks
 * English; the person may speak any of the five languages.
 */

export type ArchyAction = 'rise' | 'idle' | 'wave' | 'point' | 'explain' | 'listen' | 'ask' | 'think' | 'nod' | 'celebrate'

export interface ArchyLine {
  text: string
  action: ArchyAction
}

/** The first time someone meets Archy. */
export const archyIntro: ArchyLine[] = [
  { action: 'wave', text: "Hi! I'm Archy, Archway's voice agent." },
  { action: 'point', text: 'Tell me your app idea out loud, in your own words. I listen for English, including Indian English.' },
  { action: 'explain', text: "Take your time. When you pause for about four seconds, I'll ask if you're done, and then turn your idea into a brief for the research team." },
  { action: 'listen', text: "Go ahead, I'm listening." },
]

/** Every time after that: short. */
export const archyHello: ArchyLine[] = [{ action: 'wave', text: "Hi again! Tell me your idea. I'm listening." }]

export const archyLines = {
  ask: { action: 'ask', text: 'Got it. Shall I continue to the brief?' },
  askAgain: { action: 'ask', text: "Sorry, I didn't catch that. Should I create the brief? Just say yes or no." },
  starting: { action: 'nod', text: 'Great! Creating your brief now.' },
  done: { action: 'celebrate', text: 'Done. Your idea is saved. Give me a moment to read it.' },
  doneNew: { action: 'celebrate', text: 'I started a new project for this idea, and the brief is on its way.' },
  needMore: { action: 'think', text: 'Tell me a bit more about what you want to build.' },
  skipped: { action: 'nod', text: "No problem, I'll note that as an assumption." },
  mustAnswer: { action: 'ask', text: 'I need an answer to this one before I can go on.' },
  questionsDone: { action: 'nod', text: 'Thank you! Drafting your brief now.' },
  questionsStuck: { action: 'think', text: 'I still need an answer to continue. You can also type it in the form.' },
  generalReply: { action: 'explain', text: "I'm ARCHY, Archway's voice agent. Tell me what you want to build, and I'll turn it into a brief." },
  helloQuestions: { action: 'wave', text: "Hi! I'm Archy. Let's get your questions answered." },
  keepGoing: { action: 'nod', text: "No problem. Keep going, I'm still listening." },
  failed: { action: 'think', text: "Sorry, I couldn't save your idea. Please try again." },
} satisfies Record<string, ArchyLine>

export const archyUi = {
  name: 'ARCHY',
  role: 'Voice agent',
  activate: 'Activate voice agent ARCHY',
  turnOff: 'Click the portal to turn ARCHY off',
  sendBack: 'Send ARCHY back to the portal',
  portalOn: 'Turn off ARCHY',
  portalOff: 'Activate voice agent ARCHY',
  skipIntro: 'Skip intro',
  done: "I'm done",
  yes: 'Yes, create brief',
  no: 'Not yet',
  again: 'Speak another idea',
  tryAgain: 'Try again',
  youSaid: 'You',
  listeningHint: 'Speak whenever you are ready.',
  language: 'I listen in',
  notSetUp: 'Voice is off. Add DEEPGRAM_API_KEY to backend/.env and restart the backend.',
  micBlocked: "I can't hear you: the microphone is blocked. Allow it from the icon in the address bar, then try again.",
  micMissing: 'No microphone was found. Connect one, then try again.',
  micFailed: 'The microphone could not start. Try again.',
  status: {
    off: 'Off',
    arriving: 'Arriving',
    intro: 'Introducing',
    listening: 'Listening',
    asking: 'Asking',
    awaiting: 'Yes or no?',
    starting: 'Creating brief',
    done: 'Done',
    leaving: 'Leaving',
  },
}

/** The Voice view: every setting, in plain words. */
export const archyVoiceUi = {
  heading: 'Voice',
  lead: 'Everything about ARCHY, your voice agent: how he listens, how he sounds, and how he behaves. Changes apply at once and are remembered on this computer.',
  notSetUp: 'Voice is off. Add DEEPGRAM_API_KEY to backend/.env and restart the backend. The settings below are saved, and work as soon as voice is on.',
  sections: {
    listening: 'Listening',
    voice: 'His voice',
    speaking: 'Speaking',
    behaviour: 'Behaviour',
  },
  language: { label: 'I speak', help: 'ARCHY always answers in English; he understands all five.' },
  pause: { label: 'Pause that means "I am done"', help: 'After this much quiet, ARCHY asks if he may continue.', unit: 's' },
  fillers: { label: 'Keep "um" and "hmm" in the words', help: 'Shows you that every sound is heard. Off: they are left out.' },
  ask: { label: 'Ask before creating the brief', help: 'Off: ARCHY continues on his own once you pause.' },
  speak: { label: 'ARCHY speaks aloud', help: 'Off: his words only appear as text under the portal.' },
  speed: { label: 'Speed', slow: 'Slower', fast: 'Faster' },
  volume: { label: 'Volume' },
  intro: {
    label: 'Introduction',
    options: { first: 'The first time only', always: 'Every time', never: 'Never' },
  },
  tricks: { label: 'Play in the air while he waits', help: 'ARCHY floats on the rising air and tries tricks: skydiving, air flips, swimming. Click him to send him back to the portal.' },
  voiceFilter: { gender: 'Voice', accent: 'Accent', all: 'All', feminine: 'Female', masculine: 'Male' },
  preview: 'Preview',
  previewing: 'Playing…',
  previewLine: "Hi, I'm Archy. Tell me your idea, and I'll turn it into a brief.",
  voicesLoading: 'Loading the voices…',
  voicesFailed: 'The voices could not be loaded.',
  noVoices: 'No voice matches these filters.',
  noIndian: 'The voice service has no Indian-accent voices yet. ARCHY does understand Indian English when he listens to you.',
  tryIt: 'Hear it',
  reset: 'Reset everything',
}

/** What ARCHY says when the idea is not enough to draft a brief: he asks for more, and does not go on. */
export function elaborateLine(reason: string | null): ArchyLine {
  const lead = "That's not enough for a brief yet."
  const ask = 'Please elaborate on your idea, and then we can go on.'
  return { action: 'think', text: [lead, reason, ask].filter(Boolean).join(' ') }
}

/** What ARCHY says before reading the questions, and how he reads each one. */
export function questionsIntro(count: number): ArchyLine {
  return {
    action: 'explain',
    text: `Before I draft the brief, I have ${count === 1 ? 'one question' : `${count} quick questions`}. Answer in your own words, or say skip if you are not sure.`,
  }
}
/** After a reply that was not an answer: the question again. */
export function questionAgainLine(question: string): ArchyLine {
  return { action: 'ask', text: `Back to the question. ${question}` }
}
export function questionLine(index: number, total: number, question: string): ArchyLine {
  return { action: 'ask', text: total > 1 ? `Question ${index + 1} of ${total}. ${question}` : question }
}
