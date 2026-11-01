import { useCallback, useState } from 'react'
import { DEFAULT_SETTINGS, cleanSettings, loadSettings, saveSettings, type ArchySettings } from '../lib/voice/archySettings'

/**
 * ARCHY's settings: read once from this browser, saved on every change.
 * `change` takes only the fields that changed; everything is checked and
 * clamped before it is kept (lib/voice/archySettings.ts).
 */
export function useArchySettings() {
  const [settings, setSettings] = useState<ArchySettings>(loadSettings)

  const change = useCallback((patch: Partial<ArchySettings>) => {
    setSettings((current) => {
      const next = cleanSettings({ ...current, ...patch })
      saveSettings(next)
      return next
    })
  }, [])

  const reset = useCallback(() => {
    saveSettings(DEFAULT_SETTINGS)
    setSettings(DEFAULT_SETTINGS)
  }, [])

  return { settings, change, reset }
}
