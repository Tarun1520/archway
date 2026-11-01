/**
 * Cuts a line into short pieces that can be spoken one after another.
 *
 * Why: the voice service makes a short sentence in about a second, but a long
 * line takes several. Asking for every sentence at the same time, and playing
 * them back to back, means the first words are heard after the first sentence
 * is ready, not after the whole line is.
 */

const SHORTEST = 16 // a piece shorter than this is joined to its neighbour: tiny clips sound choppy
const LONGEST = 150

export function splitSentences(text: string): string[] {
  const clean = text.replace(/\s+/g, ' ').trim()
  if (!clean) return []
  const sentences = clean.split(/(?<=[.!?])\s+/)

  // A sentence that is too long is cut at a comma or a space near the limit.
  const pieces: string[] = []
  for (const sentence of sentences) {
    let rest = sentence
    while (rest.length > LONGEST) {
      const comma = rest.lastIndexOf(', ', LONGEST)
      const space = rest.lastIndexOf(' ', LONGEST)
      const cut = comma > SHORTEST ? comma + 1 : space > SHORTEST ? space : LONGEST
      pieces.push(rest.slice(0, cut).trim())
      rest = rest.slice(cut).trim()
    }
    if (rest) pieces.push(rest)
  }

  // Short pieces are joined to the next one (or, at the end, to the one before).
  const joined: string[] = []
  for (const piece of pieces) {
    const last = joined[joined.length - 1]
    if (last !== undefined && last.length < SHORTEST) joined[joined.length - 1] = `${last} ${piece}`
    else joined.push(piece)
  }
  if (joined.length > 1 && joined[joined.length - 1].length < SHORTEST) {
    const tail = joined.pop() as string
    joined[joined.length - 1] += ` ${tail}`
  }
  return joined
}
