/**
 * All the words on the welcome page live here, as plain data.
 *
 * The components in `components/welcome/` only decide how things look. To
 * change wording, add a step, or reorder a list, edit this file and nothing
 * else.
 *
 * TONE
 *   Confident and inviting, and every sentence says what Archway DOES.
 *   Nothing here may promise more than the product is designed to do: the
 *   numbers below are the real defaults from the implementation guide.
 */

export const navLinks = [
  { label: 'How it works', href: '#how-it-works' },
  { label: 'Why Archway', href: '#why-archway' },
  { label: 'Build pack', href: '#build-pack' },
] as const

/** The opening screen: the name and two short lines, over the picture. */
export const hero = {
  /** Read together, top to bottom: "Bring your idea / ARCHWAY / will find the path". */
  lineAbove: 'Bring your idea',
  wordmark: 'Archway',
  lineBelow: 'will find the path',
  scrollHint: 'Scroll to step inside',
}

/**
 * The second screen. In the hero's video this is what is showing on the
 * laptop, and it becomes the page as the camera reaches the screen.
 */
export const start = {
  tag: 'Start here',
  headline: 'From idea to build plan',
  summary:
    'Backed by evidence. Describe what you want to build, and Archway researches open-source projects, proposes an architecture you can inspect, and writes the prompts to build it.',
  inputLabel: 'Describe your idea',
  submitLabel: 'Start a project',
  /** Goes to the studio without starting a new project: for picking up a project already begun. */
  continueLabel: 'Continue in workspace',
  examplesLabel: 'Or start from an example',
  /** Clicking one fills the input. They are only starting points, clearly offered as examples. */
  examples: [
    'A recipe manager for my family',
    'A personal knowledge base for research papers',
    'A command-line tool that summarizes my git history',
    'A habit tracker with weekly reviews',
  ],
}

/** One large sentence that lights up word by word as it scrolls into view. */
export const statement = {
  text: 'Most projects start with a guess. Yours can start with evidence.',
}

export interface JourneyStep {
  title: string
  text: string
}

export const journey = {
  tag: 'How it works',
  heading: 'Seven steps from a sentence to a plan you can build.',
  summary: 'One clear path, and you are at the wheel for every turn.',
  steps: [
    {
      title: 'Describe',
      text: 'Say it in a sentence. Archway takes it from there.',
    },
    {
      title: 'Confirm',
      text: 'Your idea comes back as a clear brief. Shape it until it says exactly what you mean.',
    },
    {
      title: 'Research',
      text: 'Archway searches GitHub and reads the most promising projects for you, live, while you watch.',
    },
    {
      title: 'Evaluate',
      text: 'Licenses and your must-haves are checked first, so only the right candidates go forward.',
    },
    {
      title: 'Propose',
      text: 'See up to three architectures, each one built on real projects and real evidence.',
    },
    {
      title: 'Select and refine',
      text: 'Compare them side by side, pick your favourite, and tune it until it fits.',
    },
    {
      title: 'Build pack',
      text: 'Walk away with a roadmap and ready-to-run prompts for your coding agent.',
    },
  ] satisfies JourneyStep[],
}

/** The names of the steps, shown as a large band of words that slides sideways as the page scrolls. */
export const marqueeWords = journey.steps.map((step) => step.title)

export interface Figure {
  /** The number that counts up when it scrolls into view. */
  value: number
  /** Shown before the number, for limits ("up to 20"). */
  prefix?: string
  label: string
}

/** Real defaults from the implementation guide, Section 5.3. */
export const figures = {
  heading: 'Focused by design. Every run, by default:',
  items: [
    { value: 7, label: 'clear steps from idea to plan' },
    { value: 20, prefix: 'up to', label: 'open-source projects screened' },
    { value: 5, prefix: 'up to', label: 'read in depth, so you do not have to' },
    { value: 3, prefix: 'up to', label: 'architectures to choose from' },
  ] satisfies Figure[],
}

export type FeatureIcon = 'source' | 'rules' | 'steer' | 'resume'

export interface Feature {
  icon: FeatureIcon
  /** The background color of the card: one of the morning palette's names. */
  color: 'blush' | 'sky' | 'sage' | 'white'
  title: string
  text: string
}

export const features = {
  tag: 'Why Archway',
  heading: 'A plan you can trust, because you can check it.',
  items: [
    {
      icon: 'source',
      color: 'blush',
      title: 'Every claim, one click from its source.',
      text: 'See exactly where each recommendation came from: the page, the passage, and the day it was read.',
    },
    {
      icon: 'rules',
      color: 'sky',
      title: 'Rules first. Opinions second.',
      text: 'Licenses and your hard requirements are checked by plain code before any model weighs in.',
    },
    {
      icon: 'steer',
      color: 'sage',
      title: 'You stay at the wheel.',
      text: 'The brief, the choice of architecture, and the final sign-off are yours. Nothing moves on without you.',
    },
    {
      icon: 'resume',
      color: 'white',
      title: 'Pick up where you left off.',
      text: 'Close the laptop in the middle of a run. Your project is waiting, right where you paused.',
    },
  ] satisfies Feature[],
}

export interface PackEntry {
  /** How far the entry is indented: 0 for the pack folder, 1 for its contents, 2 for files inside sub-folders. */
  depth: 0 | 1 | 2
  name: string
  kind: 'folder' | 'file'
  /** What the file is for. Shown beside the name on wide screens. */
  note?: string
}

export const buildPack = {
  tag: 'Build pack',
  heading: 'A build plan your coding agent can follow.',
  summary:
    'Not one giant prompt. A sequence of small, ordered ones, each with its goal, its guard rails, and the tests that prove it worked.',
  points: [
    'Ordered by real dependencies, with the riskiest parts tested first.',
    'License notes travel with every prompt that needs them.',
    'Each step closes with a report of what changed and which tests ran.',
  ],
  exampleLabel: 'Example structure',
  entries: [
    { depth: 0, name: 'build-pack/', kind: 'folder' },
    { depth: 1, name: 'PROJECT_CONTEXT.md', kind: 'file', note: 'the confirmed brief' },
    { depth: 1, name: 'ARCHITECTURE.md', kind: 'file', note: 'version and diagram' },
    { depth: 1, name: 'DECISIONS.md', kind: 'file', note: 'choices and alternatives' },
    { depth: 1, name: 'CONSTRAINTS.md', kind: 'file', note: 'the guard rails' },
    { depth: 1, name: 'prompts/', kind: 'folder' },
    { depth: 2, name: '01_scaffold.md', kind: 'file' },
    { depth: 2, name: '02_data_and_storage.md', kind: 'file' },
    { depth: 2, name: '03_backend_features.md', kind: 'file' },
    { depth: 2, name: '04_integrations.md', kind: 'file' },
    { depth: 2, name: '05_frontend.md', kind: 'file' },
    { depth: 2, name: '06_tests_and_security.md', kind: 'file' },
    { depth: 1, name: 'verification/', kind: 'folder' },
    { depth: 2, name: 'acceptance-checklist.md', kind: 'file' },
  ] satisfies PackEntry[],
}

export const closing = {
  heading: 'Bring your idea.',
  summary: 'Archway will find the path.',
  actionLabel: 'Start a project',
}

export const footer = {
  tagline: 'From idea to build plan, backed by evidence.',
}
