/**
 * Making a model-written flowchart drawable, and readable even when it cannot be drawn.
 *
 * WHY: Mermaid reads a label like `Auth[@react-native-firebase/auth]` as syntax, not text ("@" starts a new
 * kind of shape; "/" and "(" confuse it too), and then draws nothing. Package names, paths and parentheses are
 * normal in architecture diagrams, so every node label is put in quotes first: `Auth["@react-native-firebase/auth"]`.
 * Quoting is safe for any text and harmless for text that did not need it.
 *
 * `flowFromSource` reads the arrows out of the same text, so that when drawing still fails the person can read
 * the flow as a list ("Mobile App → Auth") instead of seeing nothing.
 */

// Opening tokens, longest first, with the token that closes each.
const SHAPES: [open: string, close: string][] = [
  ['([', '])'],
  ['[(', ')]'],
  ['((', '))'],
  ['[[', ']]'],
  ['{', '}'],
  ['(', ')'],
  ['[', ']'],
]

/** Puts every node label (and every |edge label|) in quotes. Labels that are already quoted are left alone. */
export function quoteLabels(source: string): string {
  const ids = new Map<string, string>()
  return source
    .split('\n')
    .map((line, index) => (index === 0 ? line : quoteLine(giveIds(line, ids))))
    .join('\n')
}

/**
 * A node written as a bare quoted string (`"User Data" --> "Load"`) has no id, which Mermaid cannot read.
 * Seen live: a model told to quote its labels dropped the ids. Each distinct text gets one id (Q1, Q2 ...), so the
 * same text is the same node: `Q1["User Data"] --> Q2["Load"]`. A quoted label inside brackets is left alone.
 */
function giveIds(line: string, ids: Map<string, string>): string {
  let out = ''
  let depth = 0 // inside [ ( { : a quoted label there belongs to a node that already has an id
  let inEdgeLabel = false // between | and |
  let i = 0
  while (i < line.length) {
    const ch = line[i]
    if (ch === '"' && depth === 0 && !inEdgeLabel) {
      const end = line.indexOf('"', i + 1)
      if (end !== -1) {
        const text = line.slice(i + 1, end)
        if (!ids.has(text)) ids.set(text, `Q${ids.size + 1}`)
        out += `${ids.get(text)}["${text}"]`
        i = end + 1
        continue
      }
    }
    if (ch === '"') {
      // a quoted label inside brackets or an edge label: copy it whole, so brackets inside it do not count
      const end = line.indexOf('"', i + 1)
      if (end !== -1) {
        out += line.slice(i, end + 1)
        i = end + 1
        continue
      }
    }
    if ('[({'.includes(ch)) depth += 1
    else if (')]}'.includes(ch)) depth = Math.max(0, depth - 1)
    else if (ch === '|') inEdgeLabel = !inEdgeLabel
    out += ch
    i += 1
  }
  return out
}

function quoteLine(line: string): string {
  let out = ''
  let i = 0
  while (i < line.length) {
    const rest = line.slice(i)
    // An edge label: -->|text|
    const edge = /^\|([^|\n]*)\|/.exec(rest)
    if (edge && /[-=.>]$/.test(out.trimEnd())) {
      out += /^\s*".*"\s*$/.test(edge[1]) ? edge[0] : `|"${clean(edge[1])}"|` // already quoted: keep it
      i += edge[0].length
      continue
    }
    // A node: an id, then an opening bracket of some shape.
    const id = /^[A-Za-z0-9_]+/.exec(rest)
    if (id && (i === 0 || !/[A-Za-z0-9_]/.test(line[i - 1]))) {
      const afterId = rest.slice(id[0].length)
      const shape = SHAPES.find(([open]) => afterId.startsWith(open))
      if (shape) {
        const [open, close] = shape
        const end = afterId.indexOf(close, open.length)
        if (end !== -1) {
          const label = afterId.slice(open.length, end)
          out += `${id[0]}${open}${/^\s*"/.test(label) ? label : `"${clean(label)}"`}${close}`
          i += id[0].length + end + close.length
          continue
        }
      }
      out += id[0]
      i += id[0].length
      continue
    }
    out += line[i]
    i += 1
  }
  return out
}

/** A label's text made safe inside quotes: inner double quotes become single quotes. */
function clean(label: string): string {
  return label.trim().replace(/"/g, "'")
}

export interface FlowStep {
  from: string
  to: string
  label: string | null
}

/** The arrows of a flowchart, with node ids replaced by their labels, in the order written. */
export function flowFromSource(source: string): FlowStep[] {
  const names = new Map<string, string>()
  const nodeLabel = /(?:^|[\s>;|])([A-Za-z0-9_]+)(?:\(\[|\[\(|\(\(|\[\[|\{|\(|\[)\s*"?([^\]\)}"\n]*)"?\s*(?:\]\)|\)\]|\)\)|\]\]|\}|\)|\])/g
  for (const line of source.split('\n').slice(1)) {
    for (const match of line.matchAll(nodeLabel)) if (!names.has(match[1])) names.set(match[1], match[2].trim() || match[1])
  }
  const steps: FlowStep[] = []
  const edge = /([A-Za-z0-9_]+)(?:\(\[[^\n]*?\]\)|\[\([^\n]*?\)\]|\(\([^\n]*?\)\)|\[\[[^\n]*?\]\]|\{[^}\n]*\}|\([^)\n]*\)|\[[^\]\n]*\])?\s*(?:-->|---|==>|-\.->|--[ox>])\s*(?:\|"?([^|"\n]*)"?\|\s*)?([A-Za-z0-9_]+)/g
  for (const line of source.split('\n').slice(1)) {
    for (const match of line.matchAll(edge)) {
      steps.push({ from: names.get(match[1]) ?? match[1], to: names.get(match[3]) ?? match[3], label: match[2]?.trim() || null })
    }
  }
  return steps
}
