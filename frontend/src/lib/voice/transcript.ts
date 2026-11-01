/**
 * The words heard so far, while the person speaks.
 *
 * The speech service sends two kinds of results:
 *   interim  its best guess for the phrase still being spoken (it changes)
 *   final    that phrase, settled; it will not change again
 * So the text so far is: every final phrase, then the current guess.
 */
export interface Heard {
  finals: string[]
  interim: string
}

export const NOTHING_HEARD: Heard = { finals: [], interim: '' }

export function addResult(heard: Heard, text: string, final: boolean): Heard {
  const clean = text.trim()
  if (final) return { finals: clean ? [...heard.finals, clean] : heard.finals, interim: '' }
  return { ...heard, interim: clean }
}

/** Everything heard, as one piece of text. */
export function fullText(heard: Heard): string {
  return [...heard.finals, heard.interim].filter(Boolean).join(' ').trim()
}

/** Only sounds like "um" and "hmm", nothing said yet? Then there is no idea to save. */
export function onlyFillers(text: string): boolean {
  return text.replace(/\b(u+m+|h+m+|u+h+|a+h+|e+r+m*|m+)\b/gi, '').replace(/[^\p{L}\p{N}]+/gu, '').length === 0
}
