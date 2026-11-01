import { describe, expect, it } from 'vitest'
import { wantsSkip, yesOrNo } from './yesNo'

describe('yesOrNo', () => {
  it('hears a plain yes or no in English, with punctuation and capitals', () => {
    expect(yesOrNo('Yes.')).toBe('yes')
    expect(yesOrNo('Yeah, go ahead!')).toBe('yes')
    expect(yesOrNo('Okay')).toBe('yes')
    expect(yesOrNo('No.')).toBe('no')
    expect(yesOrNo('Not yet')).toBe('no')
  })

  it('lets the first answer win', () => {
    expect(yesOrNo('No, wait, okay, go ahead')).toBe('no')
    expect(yesOrNo('Yes, but hold on a second')).toBe('yes')
  })

  it('matches whole words only', () => {
    expect(yesOrNo('I know')).toBe('unclear') // "know" is not "no"
    expect(yesOrNo('nothing to add')).toBe('unclear')
    expect(yesOrNo('the notes app')).toBe('unclear')
  })

  it('understands Telugu, Kannada, Tamil and Hindi', () => {
    expect(yesOrNo('అవును')).toBe('yes')
    expect(yesOrNo('సరే.')).toBe('yes')
    expect(yesOrNo('వద్దు')).toBe('no')
    expect(yesOrNo('ಹೌದು')).toBe('yes')
    expect(yesOrNo('ಬೇಡ')).toBe('no')
    expect(yesOrNo('ஆமாம்')).toBe('yes')
    expect(yesOrNo('வேண்டாம்')).toBe('no')
    expect(yesOrNo('हाँ, ठीक है')).toBe('yes')
    expect(yesOrNo('अभी नहीं')).toBe('no')
  })

  it('says unclear when there is no answer in it', () => {
    expect(yesOrNo('')).toBe('unclear')
    expect(yesOrNo('um, hmm')).toBe('unclear')
  })
})


describe('wantsSkip', () => {
  it('hears a skip, or "I do not know", in five languages', () => {
    expect(wantsSkip('Skip.')).toBe(true)
    expect(wantsSkip("Hmm, I don't know")).toBe(true)
    expect(wantsSkip('not sure really')).toBe(true)
    expect(wantsSkip('పాస్ తెలియదు')).toBe(true)
    expect(wantsSkip('ಗೊತ್ತಿಲ್ಲ')).toBe(true)
    expect(wantsSkip('தெரியாது')).toBe(true)
    expect(wantsSkip('पता नहीं')).toBe(true)
  })

  it('does not take a real answer for a skip', () => {
    expect(wantsSkip('A mobile app for Android and iOS')).toBe(false)
    expect(wantsSkip('It should pass the messages along to everyone')).toBe(false) // a long reply that contains "pass" is a real answer
  })
})
