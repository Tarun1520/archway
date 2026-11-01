/**
 * Did the person say yes or no? Used when Archy asks "Shall I continue to the
 * brief?". Works for the five languages the user may speak in.
 *
 * The rule: find the earliest yes-phrase and the earliest no-phrase in what
 * was heard; whichever comes first wins ("no, wait" is a no, "yes, go
 * ahead" is a yes). Neither means 'unclear', and Archy asks again.
 */
export type Answer = 'yes' | 'no' | 'unclear'

const YES = [
  // English
  'yes', 'yeah', 'yep', 'yup', 'ya', 'sure', 'ok', 'okay', 'go ahead', 'continue', 'do it', 'of course',
  'absolutely', 'please do', 'go on', "let's go", 'lets go', 'correct', 'right', 'yes please', 'definitely',
  // Telugu
  'అవును', 'ఔను', 'సరే', 'అవునండి', 'సరేనండి', 'కానివ్వు', 'చేయి', 'చెయ్యి',
  // Kannada
  'ಹೌದು', 'ಸರಿ', 'ಆಯ್ತು', 'ಮುಂದುವರಿಸಿ', 'ಮಾಡಿ',
  // Tamil
  'ஆமா', 'ஆம்', 'ஆமாம்', 'சரி', 'தொடரவும்', 'செய்',
  // Hindi
  'हाँ', 'हां', 'हा', 'जी', 'जी हाँ', 'ठीक है', 'ठीक', 'चलो', 'बिल्कुल', 'करो',
]

const NO = [
  // English
  'no', 'nope', 'nah', 'not yet', 'wait', 'stop', 'hold on', "don't", 'dont', 'not now', 'cancel', 'later', 'never mind',
  // Telugu
  'వద్దు', 'లేదు', 'ఆగు', 'ఆగండి', 'ఇంకా లేదు',
  // Kannada
  'ಬೇಡ', 'ಇಲ್ಲ', 'ನಿಲ್ಲಿಸಿ', 'ಇನ್ನೂ ಇಲ್ಲ',
  // Tamil
  'வேண்டாம்', 'இல்லை', 'இல்ல', 'நில்', 'காத்திரு',
  // Hindi
  'नहीं', 'नही', 'मत', 'रुको', 'अभी नहीं', 'ना',
]

/** Lower case, punctuation turned into spaces, single spaces, padded so phrases match whole words. */
function normalise(text: string): string {
  const plain = text.toLowerCase().replace(/[’`]/g, "'").replace(/[^\p{L}\p{M}\p{N}' ]+/gu, ' ')
  return ` ${plain.replace(/\s+/g, ' ').trim()} `
}

/** Where the earliest of these phrases starts, as a whole word or words; Infinity if none is there. */
function earliest(text: string, phrases: string[]): number {
  let best = Infinity
  for (const phrase of phrases) {
    const at = text.indexOf(` ${phrase} `)
    if (at !== -1 && at < best) best = at
  }
  return best
}

export function yesOrNo(heard: string): Answer {
  const text = normalise(heard)
  const yes = earliest(text, YES)
  const no = earliest(text, NO)
  if (yes === Infinity && no === Infinity) return 'unclear'
  return yes < no ? 'yes' : 'no'
}


// --- Skipping a question ---------------------------------------------------------------

const SKIP = [
  // English
  'skip', 'pass', 'next', 'no idea', 'not sure', 'unsure', "i don't know", 'i dont know', "don't know", 'dont know', 'nothing', 'none',
  // Telugu
  'తెలియదు', 'స్కిప్',
  // Kannada
  'ಗೊತ್ತಿಲ್ಲ', 'ಸ್ಕಿಪ್',
  // Tamil
  'தெரியாது', 'தெரியல', 'ஸ்கிப்',
  // Hindi
  'पता नहीं', 'छोड़ो', 'छोड़ दो', 'स्किप',
]

/** A skip is a short reply. A longer one that merely contains "pass" or "next" is a real answer. */
const SKIP_MAX_WORDS = 5

/** Did the person say they want to skip this question (or do not know)? */
export function wantsSkip(heard: string): boolean {
  const text = normalise(heard)
  if (text.trim().split(' ').length > SKIP_MAX_WORDS) return false
  return SKIP.some((phrase) => text.includes(` ${phrase} `))
}
