import { describe, expect, it } from 'vitest'
import type { PlanSnapshot, PlanTask } from './api/types'
import { NODE_HEIGHT, layoutPlanFlow, type FlowLayout } from './planFlow'

const task = (id: string, stage: PlanTask['stage'], over: Partial<PlanTask> = {}): PlanTask => ({
  id, title: `Task ${id}`, goal: '', stage, kind: 'build', prerequisites: [], scope: '', out_of_scope: [], likely_files: [],
  interfaces_to_preserve: [], requirement_ids: [], components: [], evidence_ids: [], acceptance_criteria: [], validation_steps: [],
  risks: [], validates: [], ...over,
})
const prompt = (path: string, task_ids: string[]) => ({ path, title: path, kind: 'prompt' as const, content: '', task_ids, prerequisites: [], rubric: [] })

const makePlan = (tasks: PlanTask[]): PlanSnapshot => ({
  requested: true, built_for: null, approved: null, stale: false, passed: true, outcome: 'full', notes: [], completed: [],
  roadmap: { architecture: { id: 'OPT-1', version: 1 }, brief_version: 1, decisions: [], tasks },
  files: [
    prompt('prompts/01_scaffold.md', ['T-01']),
    prompt('prompts/02_integrations.md', ['T-02', 'T-03']),
    prompt('prompts/03_backend_features.md', ['T-04']),
  ],
  links: [
    { requirement_id: 'REQ-1', requirement: 'Do the thing', coverage: 'covered', task_ids: ['T-04'], components: [] },
    { requirement_id: 'REQ-2', requirement: 'Also this', coverage: 'unknown', task_ids: [], components: [] },
  ],
}) as PlanSnapshot

const TASKS = [
  task('T-01', 'scaffold'),
  task('T-02', 'integrations', { kind: 'spike', prerequisites: ['T-01'] }),
  task('T-03', 'integrations', { prerequisites: ['T-01', 'T-02'] }),
  task('T-04', 'backend_features', { prerequisites: ['T-03'], requirement_ids: ['REQ-1'] }),
]

/** Does any box (other than the arrow's own two) lie on the arrow's path? Sampled along the path's points. */
function crossesABox(layout: FlowLayout, arrowId: string): boolean {
  const arrow = layout.arrows.find((a) => a.id === arrowId)!
  const points = [...arrow.path.matchAll(/(-?\d+(?:\.\d+)?) (-?\d+(?:\.\d+)?)/g)].map((m) => [Number(m[1]), Number(m[2])])
  const segments: number[][] = []
  for (let i = 1; i < points.length; i++) for (let t = 0; t <= 1; t += 0.1) segments.push([points[i - 1][0] + (points[i][0] - points[i - 1][0]) * t, points[i - 1][1] + (points[i][1] - points[i - 1][1]) * t])
  return layout.nodes.some((n) => n.id !== arrow.from && n.id !== arrow.to
    && segments.some(([x, y]) => x > n.x + 1 && x < n.x + n.width - 1 && y > n.y + 1 && y < n.y + NODE_HEIGHT - 1))
}

describe('layoutPlanFlow (top to bottom)', () => {
  const wide = layoutPlanFlow(makePlan(TASKS), 1000)

  it('makes one band per prompt in build order, going down, then the requirements', () => {
    expect(wide.bands.map((b) => b.path)).toEqual(['prompts/01_scaffold.md', 'prompts/02_integrations.md', 'prompts/03_backend_features.md', null])
    expect(wide.bands.map((b) => b.y)).toEqual([...wide.bands.map((b) => b.y)].sort((a, b) => a - b))
    const band = Object.fromEntries(wide.nodes.map((n) => [n.id, n.band]))
    expect(band).toEqual({ 'T-01': 0, 'T-02': 1, 'T-03': 1, 'T-04': 2, 'REQ-1': 3, 'REQ-2': 3 })
  })

  it('always fits the width it is given: nothing to scroll sideways', () => {
    for (const width of [1000, 600, 343]) {
      const layout = layoutPlanFlow(makePlan(TASKS), width)
      expect(layout.width).toBeLessThanOrEqual(Math.max(width, 180 + 40))
      for (const node of layout.nodes) expect(node.x + node.width).toBeLessThanOrEqual(layout.width)
    }
  })

  it('stacks the tasks of a band on a narrow screen', () => {
    const narrow = layoutPlanFlow(makePlan(TASKS), 343)
    const t2 = narrow.nodes.find((n) => n.id === 'T-02')!
    const t3 = narrow.nodes.find((n) => n.id === 'T-03')!
    expect(t3.y).toBeGreaterThan(t2.y)
  })

  it('shows a requirement no task delivers, marked as such, instead of hiding it', () => {
    expect(wide.nodes.find((n) => n.id === 'REQ-2')?.delivered).toBe(false)
  })

  it('draws only the arrows that say something, timed by the band they point to', () => {
    // T-01 -> T-03 is left out: T-03 needs T-02, which already needs T-01.
    expect(wide.arrows.map((a) => [a.id, a.band])).toEqual([['T-01->T-02', 1], ['T-02->T-03', 1], ['T-03->T-04', 2], ['T-04->REQ-1', 3]])
  })

  it('never draws an arrow behind a box, wide or narrow, even when an arrow jumps over bands', () => {
    const jumping = TASKS.map((t) => (t.id === 'T-04' ? { ...t, prerequisites: ['T-01', 'T-03'] } : t))
    jumping[3] = { ...jumping[3], prerequisites: ['T-01'] } // T-04 now needs only T-01: a jump over the integrations band
    for (const width of [1000, 343]) {
      const layout = layoutPlanFlow(makePlan(jumping), width)
      for (const arrow of layout.arrows) expect(crossesABox(layout, arrow.id), `${arrow.id} at ${width}px`).toBe(false)
    }
  })
})
