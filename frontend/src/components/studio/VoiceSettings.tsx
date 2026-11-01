import { useEffect, useMemo, useState } from 'react'
import type { ReactNode } from 'react'
import { archyVoiceUi as copy } from '../../content/archy'
import { listVoices, type VoiceOption } from '../../lib/api/client'
import { LIMITS, type ArchySettings, type IntroMode } from '../../lib/voice/archySettings'
import { hush, primeSpeaker, say } from '../../lib/voice/speaker'

interface VoiceSettingsProps {
  settings: ArchySettings
  onChange: (patch: Partial<ArchySettings>) => void
  onReset: () => void
  /** Whether the backend can speak and listen at all. */
  available: boolean
}

type GenderFilter = 'all' | 'feminine' | 'masculine'

/**
 * The Voice view: every setting for ARCHY on one page. Each control saves the
 * moment it changes (useArchySettings). The voice list comes from the voice
 * service's own catalogue (name, accent, gender and style of every voice), and
 * each voice can be heard before it is chosen.
 */
export function VoiceSettings({ settings, onChange, onReset, available }: VoiceSettingsProps) {
  const [voices, setVoices] = useState<VoiceOption[] | null>(null)
  const [failed, setFailed] = useState(false)
  const [gender, setGender] = useState<GenderFilter>('all')
  const [accent, setAccent] = useState('all')
  const [playing, setPlaying] = useState<string | null>(null)

  useEffect(() => {
    if (!available) return
    let cancelled = false
    listVoices()
      .then((list) => !cancelled && setVoices(list))
      .catch(() => !cancelled && setFailed(true))
    return () => {
      cancelled = true
    }
  }, [available])

  const accents = useMemo(() => ['all', ...new Set((voices ?? []).map((voice) => voice.accent))], [voices])
  const shown = (voices ?? []).filter((voice) => (gender === 'all' || voice.gender === gender) && (accent === 'all' || voice.accent === accent))

  /** Plays a line in a voice, with the current speed and volume. Clicking it again stops it. */
  const hear = async (voice: string) => {
    primeSpeaker() // inside the click, so the browser lets it play
    if (playing === voice) {
      setPlaying(null)
      hush()
      return
    }
    setPlaying(voice)
    await say(copy.previewLine, { voice, speed: settings.speed, volume: settings.volume })
    setPlaying((now) => (now === voice ? null : now))
  }

  return (
    <div className="flex max-w-[980px] flex-col gap-40">
      <div>
        <h2 className="text-h3 font-bold text-chalk md:text-h2">{copy.heading}</h2>
        <p className="mt-12 max-w-2xl text-lead text-smoke">{copy.lead}</p>
        {!available && <p className="mt-16 max-w-2xl border-l-2 border-vermilion py-4 pl-16 text-[15px] text-chalk">{copy.notSetUp}</p>}
      </div>

      {/* --- Listening ------------------------------------------------------------ */}
      <Section title={copy.sections.listening}>
        <Row label={copy.pause.label} help={copy.pause.help}>
          <Slider
            label={copy.pause.label}
            value={settings.pauseSeconds}
            {...LIMITS.pauseSeconds}
            display={`${settings.pauseSeconds} ${copy.pause.unit}`}
            onChange={(value) => onChange({ pauseSeconds: value })}
          />
        </Row>
      </Section>

      {/* --- His voice -------------------------------------------------------------- */}
      <Section title={copy.sections.voice}>
        <div className="flex flex-wrap items-center gap-x-32 gap-y-12">
          <div role="radiogroup" aria-label={copy.voiceFilter.gender} className="flex flex-wrap items-center gap-8">
            <span className="mr-4 font-code text-label uppercase text-smoke">{copy.voiceFilter.gender}</span>
            {(['all', 'feminine', 'masculine'] as const).map((value) => (
              <Choice key={value} selected={gender === value} onClick={() => setGender(value)}>
                {copy.voiceFilter[value]}
              </Choice>
            ))}
          </div>
          {accents.length > 2 && (
            <div role="radiogroup" aria-label={copy.voiceFilter.accent} className="flex flex-wrap items-center gap-8">
              <span className="mr-4 font-code text-label uppercase text-smoke">{copy.voiceFilter.accent}</span>
              {accents.map((value) => (
                <Choice key={value} selected={accent === value} onClick={() => setAccent(value)}>
                  {value === 'all' ? copy.voiceFilter.all : value}
                </Choice>
              ))}
            </div>
          )}
        </div>

        {voices && !accents.some((value) => /india/i.test(value)) && <p className="max-w-2xl text-[13px] leading-[1.5] text-smoke">{copy.noIndian}</p>}
        {available && !voices && !failed && <p className="text-[15px] text-smoke">{copy.voicesLoading}</p>}
        {failed && <p className="text-[15px] text-vermilion">{copy.voicesFailed}</p>}
        {voices && shown.length === 0 && <p className="text-[15px] text-smoke">{copy.noVoices}</p>}

        <ul className="grid gap-12 sm:grid-cols-2 lg:grid-cols-3">
          {shown.map((voice) => {
            const chosen = settings.voice === voice.id
            return (
              <li
                key={voice.id}
                className={`flex flex-col gap-10 rounded-card border p-16 transition-colors ${
                  chosen ? 'border-chalk bg-soot/70' : 'border-line bg-carbon/60 hover:border-slate'
                }`}
              >
                <button
                  type="button"
                  onClick={() => onChange({ voice: voice.id })}
                  aria-pressed={chosen}
                  className="flex flex-col gap-4 rounded-control text-left focus-visible:outline-2 focus-visible:outline-vermilion"
                >
                  <span className="flex items-center justify-between gap-8">
                    <span className="text-[18px] font-semibold text-chalk">{voice.name}</span>
                    {chosen && <span className="font-code text-label uppercase text-vermilion">✓</span>}
                  </span>
                  <span className="font-code text-label uppercase text-smoke">
                    {voice.gender === 'feminine' ? copy.voiceFilter.feminine : copy.voiceFilter.masculine} · {voice.accent} · {voice.age}
                  </span>
                  <span className="text-[13px] leading-[1.5] text-chalk/70">{voice.tags.slice(0, 4).join(', ')}</span>
                </button>
                <button
                  type="button"
                  onClick={() => void hear(voice.id)}
                  disabled={!available}
                  className="h-36 w-fit rounded-pill border border-line px-14 text-[13px] font-medium text-chalk transition-colors hover:bg-soot disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-vermilion"
                >
                  {playing === voice.id ? `■ ${copy.previewing}` : `▶ ${copy.preview}`}
                </button>
              </li>
            )
          })}
        </ul>
      </Section>

      {/* --- Speaking ------------------------------------------------------------------ */}
      <Section title={copy.sections.speaking}>
        <Row label={copy.speak.label} help={copy.speak.help}>
          <Toggle label={copy.speak.label} on={settings.speak} onChange={(on) => onChange({ speak: on })} />
        </Row>
        <Row label={copy.speed.label}>
          <Slider
            label={copy.speed.label}
            value={settings.speed}
            {...LIMITS.speed}
            display={`${settings.speed.toFixed(2)}×`}
            ends={[copy.speed.slow, copy.speed.fast]}
            onChange={(value) => onChange({ speed: Math.round(value * 100) / 100 })}
          />
        </Row>
        <Row label={copy.volume.label}>
          <Slider
            label={copy.volume.label}
            value={settings.volume}
            {...LIMITS.volume}
            display={`${Math.round(settings.volume * 100)}%`}
            onChange={(value) => onChange({ volume: Math.round(value * 100) / 100 })}
          />
        </Row>
        <div>
          <button
            type="button"
            onClick={() => void hear(settings.voice)}
            disabled={!available}
            className="h-44 rounded-pill bg-chalk px-24 text-[15px] font-semibold text-void transition-transform hover:scale-[1.03] disabled:opacity-40 focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-vermilion"
          >
            {playing === settings.voice ? `■ ${copy.previewing}` : `▶ ${copy.tryIt}`}
          </button>
        </div>
      </Section>

      {/* --- Behaviour ------------------------------------------------------------------ */}
      <Section title={copy.sections.behaviour}>
        <Row label={copy.intro.label}>
          <div role="radiogroup" aria-label={copy.intro.label} className="flex flex-wrap gap-8">
            {(['first', 'always', 'never'] as IntroMode[]).map((mode) => (
              <Choice key={mode} selected={settings.intro === mode} onClick={() => onChange({ intro: mode })}>
                {copy.intro.options[mode]}
              </Choice>
            ))}
          </div>
        </Row>
        <Row label={copy.tricks.label} help={copy.tricks.help}>
          <Toggle label={copy.tricks.label} on={settings.tricks} onChange={(on) => onChange({ tricks: on })} />
        </Row>
      </Section>

      <div>
        <button
          type="button"
          onClick={onReset}
          className="min-h-44 font-code text-label uppercase text-smoke underline decoration-line decoration-2 underline-offset-[6px] transition-colors hover:text-chalk hover:decoration-vermilion focus-visible:outline-2 focus-visible:outline-vermilion"
        >
          {copy.reset}
        </button>
      </div>
    </div>
  )
}

// --- Small building blocks ---------------------------------------------------------

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-20 border-t border-line pt-24">
      <h3 className="font-code text-label uppercase text-smoke">{title}</h3>
      {children}
    </section>
  )
}

function Row({ label, help, children }: { label: string; help?: string; children: ReactNode }) {
  return (
    <div className="grid gap-8 md:grid-cols-[minmax(0,320px)_1fr] md:items-center md:gap-32">
      <div>
        <p className="text-[16px] font-medium text-chalk">{label}</p>
        {help && <p className="mt-2 text-[13px] leading-[1.5] text-smoke">{help}</p>}
      </div>
      <div>{children}</div>
    </div>
  )
}

function Choice({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: ReactNode }) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onClick}
      className={`h-36 rounded-pill px-14 text-[14px] transition-colors focus-visible:outline-2 focus-visible:outline-vermilion ${
        selected ? 'bg-chalk font-medium text-void' : 'border border-line text-chalk/80 hover:bg-soot hover:text-chalk'
      }`}
    >
      {children}
    </button>
  )
}

function Toggle({ on, onChange, label }: { on: boolean; onChange: (on: boolean) => void; label: string }) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={on}
      aria-label={label}
      onClick={() => onChange(!on)}
      className={`relative h-28 w-52 rounded-pill transition-colors focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-vermilion ${on ? 'bg-chalk' : 'bg-soot'}`}
    >
      <span className={`absolute top-4 size-20 rounded-pill transition-all duration-200 ${on ? 'left-[28px] bg-void' : 'left-4 bg-smoke'}`} />
    </button>
  )
}

function Slider({
  label, value, min, max, step, display, ends, onChange,
}: {
  label: string
  value: number
  min: number
  max: number
  step: number
  display: string
  ends?: [string, string]
  onChange: (value: number) => void
}) {
  return (
    <div className="flex max-w-[420px] flex-col gap-4">
      <div className="flex items-center gap-16">
        <input
          type="range"
          aria-label={label}
          min={min}
          max={max}
          step={step}
          value={value}
          onChange={(event) => onChange(Number(event.target.value))}
          className="h-24 min-w-0 flex-1 cursor-pointer accent-[#fafafa]"
        />
        <span className="w-56 text-right font-code text-[13px] text-chalk">{display}</span>
      </div>
      {ends && (
        <div className="flex justify-between font-code text-[11px] uppercase text-smoke">
          <span>{ends[0]}</span>
          <span>{ends[1]}</span>
        </div>
      )}
    </div>
  )
}
