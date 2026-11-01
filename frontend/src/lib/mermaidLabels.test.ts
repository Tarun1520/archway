import { describe, expect, it } from 'vitest'
import { flowFromSource, quoteLabels } from './mermaidLabels'

const FAILED = `flowchart LR
  UserDevice[Mobile App] --> Auth[@react-native-firebase/auth]
  UserDevice --> FS[@react-native-firebase/firestore]
  UserDevice --> Crypto[TweetNaCl.js]
  UserDevice --> FCM[Firebase Cloud Messaging]
  Crypto --> FS
  FS --> UserDevice
  Auth --> FS`

describe('quoteLabels', () => {
  it('quotes labels with @ and slashes, which Mermaid cannot read bare', () => {
    const out = quoteLabels(FAILED)
    expect(out).toContain('Auth["@react-native-firebase/auth"]')
    expect(out).toContain('UserDevice["Mobile App"]')
    expect(out).toContain('Crypto["TweetNaCl.js"]')
    expect(out.split('\n')[0]).toBe('flowchart LR')
  })

  it('handles every shape and keeps the arrows', () => {
    const out = quoteLabels('flowchart LR\nA[(Local DB)] --> B([Queue (retry)])\nB --> C{Ok?}\nC -->|yes, sync| D((Done))\nD --> E[[Sub/part]]')
    expect(out).toContain('A[("Local DB")]')
    expect(out).toContain('B(["Queue (retry)"])')
    expect(out).toContain('C{"Ok?"}')
    expect(out).toContain('-->|"yes, sync"|')
    expect(out).toContain('D(("Done"))')
    expect(out).toContain('E[["Sub/part"]]')
  })

  it('leaves already quoted labels alone, so it can run twice', () => {
    const once = quoteLabels(FAILED)
    expect(quoteLabels(once)).toBe(once)
  })

  it('turns double quotes inside a label into single quotes', () => {
    expect(quoteLabels('flowchart LR\nA[say "hi"] --> B')).toContain('A["say \'hi\'"]')
  })
})

describe('flowFromSource', () => {
  it('reads the arrows with the labels, not the ids', () => {
    const steps = flowFromSource(FAILED)
    expect(steps[0]).toEqual({ from: 'Mobile App', to: '@react-native-firebase/auth', label: null })
    expect(steps.some((s) => s.from === 'TweetNaCl.js' && s.to === '@react-native-firebase/firestore')).toBe(true)
    expect(steps).toHaveLength(7)
  })

  it('keeps edge labels and works on quoted text too', () => {
    const steps = flowFromSource(quoteLabels('flowchart LR\nA[App] -->|upload| B[(DB)]'))
    expect(steps).toEqual([{ from: 'App', to: 'DB', label: 'upload' }])
  })
})


describe('bare quoted nodes (seen live)', () => {
  const BARE = 'flowchart LR\n  "User Data" --> "Pandas Load"\n  "Pandas Load" --> "Model (sklearn/xgboost)"\n  "Pandas Load" -->|"split"| "Val/Test Data"'

  it('gives each distinct text one id, so the same text stays the same node', () => {
    const out = quoteLabels(BARE)
    expect(out).toContain('Q1["User Data"] --> Q2["Pandas Load"]')
    expect(out).toContain('Q2["Pandas Load"] --> Q3["Model (sklearn/xgboost)"]')
    expect(out).toContain('-->|"split"| Q4["Val/Test Data"]')
  })

  it('reads the flow from them', () => {
    expect(flowFromSource(quoteLabels(BARE))[0]).toEqual({ from: 'User Data', to: 'Pandas Load', label: null })
  })
})
