/**
 * The layout of the build flow chart (components/studio/plan/PlanFlow.tsx), as plain functions.
 *
 * The chart reads TOP TO BOTTOM and always fits the width it is given (the page never scrolls sideways):
 *
 *   bands     one per prompt, in build order (01 Scaffold at the top), each holding its tasks side by side; tasks
 *             that do not fit wrap onto the next row of the band. The last band holds the requirements the tasks
 *             deliver.
 *   arrows    from every prerequisite to the task that needs it, and from a task to each requirement it delivers
 *
 * How an arrow is drawn, so that it never passes behind a box it does not belong to:
 *   - into the very next row (the next band, or the next row of a wrapped band): straight down, bottom to top
 *   - between two boxes on the same row (a spike before the task that relies on it): an arc over the row
 *   - anything farther: down into the gap below the source's row, along it to a lane in the gutter on the right, down
 *     the lane, back along the gap above the target's row, and down into it. Arrows whose spans do not overlap share
 *     a lane, so the gutter stays narrow.
 *
 * The gutter takes width, which can change how bands wrap, which changes which arrows need a lane: so the layout is
 * repeated (at most a few times) until the gutter it needs is the gutter it was given.
 *
 * Only the arrows that say something are drawn: when A comes before B and B before C, the arrow A -> C is left out
 * (it is implied). This is a "transitive reduction" of the prerequisites.
 *
 * Every node and arrow carries the band it belongs to, so the chart can draw itself in build order.
 */
import type { PlanSnapshot, PlanTask } from './api/types'

export const MAX_NODE_WIDTH = 236
export const MIN_NODE_WIDTH = 180
export const NODE_HEIGHT = 112
export const NODE_GAP = 28 // between boxes on one row
export const ROW_GAP = 44 // between the rows of one band (room for an arrow)
export const BAND_HEADER = 56 // the band's title, and room for an arc over its first row
export const BAND_GAP = 40 // between bands (room for the arrows going down)
export const ARC = 18 // how high an arrow between boxes on the same row arcs
export const LANE_GAP = 12 // between two lanes in the right gutter
export const GUTTER_PAD = 16 // between the boxes and the first lane

export interface FlowNode {
  id: string
  kind: 'task' | 'requirement'
  band: number
  row: number // the row inside its band
  slot: number // the position on that row
  x: number
  y: number
  width: number
  task?: PlanTask
  /** For a requirement: its text, and whether any task delivers it. */
  text?: string
  delivered?: boolean
}

export interface FlowBand {
  index: number
  title: string
  /** The prompt file this band is, or null for the requirements band. */
  path: string | null
  y: number
}

export interface FlowArrow {
  id: string
  from: string
  to: string
  path: string
  /** The band of the node the arrow points to: it is drawn when that band appears. */
  band: number
  kind: 'prerequisite' | 'delivers'
}

export interface FlowLayout {
  bands: FlowBand[]
  nodes: FlowNode[]
  arrows: FlowArrow[]
  width: number
  height: number
}

type Item = Pick<FlowNode, 'id' | 'kind' | 'task' | 'text' | 'delivered'>

/** Lays the plan out for a drawing area `width` pixels wide. */
export function layoutPlanFlow(plan: PlanSnapshot, width: number): FlowLayout {
  const tasks = new Map((plan.roadmap?.tasks ?? []).map((task) => [task.id, task]))
  const prompts = plan.files.filter((file) => file.kind === 'prompt')
  const groups: { title: string; path: string | null; items: Item[] }[] = prompts.map((prompt) => ({
    title: prompt.title,
    path: prompt.path,
    items: prompt.task_ids.filter((id) => tasks.has(id)).map((id) => ({ id, kind: 'task' as const, task: tasks.get(id) })),
  }))
  // Requirements last: every one the plan links, delivered or not (an undelivered one is shown, never hidden).
  const requirements = plan.links.map((link) => ({
    id: link.requirement_id, kind: 'requirement' as const, text: link.requirement, delivered: link.task_ids.length > 0,
  }))
  if (requirements.length > 0) groups.push({ title: 'Delivers', path: null, items: requirements })

  const bandOf = new Map<string, number>()
  groups.forEach((group, band) => group.items.forEach((item) => bandOf.set(item.id, band)))
  const needs = reducedPrerequisites([...tasks.values()])
  const links: { from: string; to: string; kind: FlowArrow['kind'] }[] = []
  for (const group of groups) {
    for (const item of group.items) {
      if (!item.task) continue
      for (const prerequisite of needs.get(item.id) ?? []) if (bandOf.has(prerequisite)) links.push({ from: prerequisite, to: item.id, kind: 'prerequisite' })
      for (const requirement of item.task.requirement_ids) if (bandOf.has(requirement)) links.push({ from: item.id, to: requirement, kind: 'delivers' })
    }
  }
  let gutter = 0
  let result = place(groups, links, width, gutter)
  for (let attempt = 0; attempt < 4 && result.gutter !== gutter; attempt++) {
    gutter = result.gutter
    result = place(groups, links, width, gutter)
  }
  return result.layout
}

/** One layout attempt for a given gutter width; also says which gutter its arrows would need. */
function place(
  groups: { title: string; path: string | null; items: Item[] }[],
  links: { from: string; to: string; kind: FlowArrow['kind'] }[],
  width: number,
  gutter: number,
): { layout: FlowLayout; gutter: number } {
  // How many boxes fit on one row, and how wide they are.
  const room = Math.max(MIN_NODE_WIDTH, width - gutter)
  const perRow = Math.max(1, Math.floor((room + NODE_GAP) / (MIN_NODE_WIDTH + NODE_GAP)))
  const widest = Math.max(1, ...groups.map((group) => group.items.length))
  const columns = Math.min(perRow, widest)
  const nodeWidth = Math.min(MAX_NODE_WIDTH, Math.floor((room - (columns - 1) * NODE_GAP) / columns))
  const contentWidth = columns * nodeWidth + (columns - 1) * NODE_GAP

  const nodes: FlowNode[] = []
  const bands: FlowBand[] = []
  const rowNumber = new Map<string, number>() // the row of each node, counted over the whole chart
  let y = 0
  let rowsBefore = 0
  groups.forEach((group, band) => {
    bands.push({ index: band, title: group.title, path: group.path, y })
    const top = y + BAND_HEADER
    const rows = Math.ceil(group.items.length / columns)
    group.items.forEach((item, index) => {
      const row = Math.floor(index / columns)
      const slot = index % columns
      // A row that is not full is centred, so a band of one task sits in the middle of the flow.
      const onRow = Math.min(columns, group.items.length - row * columns)
      const offset = (contentWidth - (onRow * nodeWidth + (onRow - 1) * NODE_GAP)) / 2
      nodes.push({ ...item, band, row, slot, width: nodeWidth, x: offset + slot * (nodeWidth + NODE_GAP), y: top + row * (NODE_HEIGHT + ROW_GAP) })
      rowNumber.set(item.id, rowsBefore + row)
    })
    rowsBefore += rows
    y = top + rows * NODE_HEIGHT + (rows - 1) * ROW_GAP + BAND_GAP
  })

  // Which arrows need a lane, and which lane: arrows whose spans do not overlap share one.
  const byId = new Map(nodes.map((node) => [node.id, node]))
  const needsLane = (link: { from: string; to: string }) => {
    const step = rowNumber.get(link.to)! - rowNumber.get(link.from)!
    return step !== 0 && step !== 1
  }
  const laneOf = new Map<string, number>()
  const laneEnds: number[] = []
  const lanes = links.filter(needsLane).map((link) => ({ link, top: byId.get(link.from)!.y, bottom: byId.get(link.to)!.y + NODE_HEIGHT }))
  lanes.sort((a, b) => a.top - b.top)
  for (const { link, top, bottom } of lanes) {
    let lane = laneEnds.findIndex((end) => end < top)
    if (lane === -1) lane = laneEnds.push(bottom) - 1
    else laneEnds[lane] = bottom
    laneOf.set(`${link.from}->${link.to}`, lane)
  }

  const arrows: FlowArrow[] = links.map(({ from, to, kind }) => {
    const id = `${from}->${to}`
    const lane = laneOf.get(id)
    const laneX = lane === undefined ? null : contentWidth + GUTTER_PAD + lane * LANE_GAP
    return { id, from, to, path: arrowPath(byId.get(from)!, byId.get(to)!, laneX), band: byId.get(to)!.band, kind }
  })
  const used = laneEnds.length ? GUTTER_PAD + laneEnds.length * LANE_GAP : 0
  return {
    layout: { bands, nodes, arrows, width: contentWidth + used, height: Math.max(0, y - BAND_GAP + 8) },
    gutter: used,
  }
}

/** Each task's prerequisites without the implied ones: a prerequisite that another prerequisite already needs. */
export function reducedPrerequisites(tasks: PlanTask[]): Map<string, string[]> {
  const direct = new Map(tasks.map((task) => [task.id, task.prerequisites]))
  const reaches = (start: string, goal: string): boolean => {
    const seen = new Set<string>()
    const todo = [...(direct.get(start) ?? [])]
    while (todo.length) {
      const id = todo.pop()!
      if (id === goal) return true
      if (!seen.has(id)) {
        seen.add(id)
        todo.push(...(direct.get(id) ?? []))
      }
    }
    return false
  }
  return new Map(tasks.map((task) => [
    task.id,
    task.prerequisites.filter((p) => !task.prerequisites.some((other) => other !== p && reaches(other, p))),
  ]))
}

/** The curve of one arrow (an SVG path). `laneX`: the lane in the right gutter, for an arrow that jumps a band. */
export function arrowPath(from: FlowNode, to: FlowNode, laneX: number | null = null): string {
  if (laneX !== null) {
    // Down out of the source into the empty gap below its row, right to the lane, down the lane, left along the empty
    // gap above the target's row, and down into the target. Every sideways stretch runs in a gap between rows.
    const x1 = from.x + from.width / 2
    const x2 = to.x + to.width / 2
    const below = from.y + NODE_HEIGHT + 14
    const above = to.y - 16
    const r = 8
    return `M ${x1} ${from.y + NODE_HEIGHT} L ${x1} ${below - r} Q ${x1} ${below}, ${x1 + r} ${below} L ${laneX - r} ${below} `
      + `Q ${laneX} ${below}, ${laneX} ${below + r} L ${laneX} ${above - r} Q ${laneX} ${above}, ${laneX - r} ${above} `
      + `L ${x2 + r} ${above} Q ${x2} ${above}, ${x2} ${above + r} L ${x2} ${to.y}`
  }
  if (from.band === to.band && from.row === to.row) {
    // Side by side on one row: an arc over the top, from one box's top to the other's.
    const x1 = from.x + from.width / 2
    const x2 = to.x + to.width / 2
    const y = from.y
    return `M ${x1} ${y} C ${x1} ${y - ARC * 1.6}, ${x2} ${y - ARC * 1.6}, ${x2} ${y}`
  }
  // Downwards: bottom of the source to the top of the target.
  const x1 = from.x + from.width / 2
  const y1 = from.y + NODE_HEIGHT
  const x2 = to.x + to.width / 2
  const y2 = to.y
  const pull = Math.max(18, (y2 - y1) * 0.5)
  return `M ${x1} ${y1} C ${x1} ${y1 + pull}, ${x2} ${y2 - pull}, ${x2} ${y2}`
}
