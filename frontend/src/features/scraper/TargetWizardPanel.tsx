import { useMutation } from '@tanstack/react-query'
import { Loader2, Sparkles, Wand2 } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { parseConfigJson, platformLabel, targetTypeLabelLong } from '@/features/scraper/utils'
import { getApiErrorMessage } from '@/shared/api/errors'
import {
  wizardCreateTarget,
  wizardDetectPlatform,
  WizardConflictError,
  type WizardSuggestedConfig,
} from '@/shared/api/wizard'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { Input } from '@/shared/components/Input'
import { Select } from '@/shared/components/Select'
import { StatusBadge } from '@/shared/components/StatusBadge'

type TargetWizardPanelProps = {
  mode: 'create' | 'assist'
  initialUrl?: string
  onCreated?: (targetId: number) => void
  onApplySuggestion?: (suggestion: {
    name: string
    startUrl: string
    targetType: string
    enabled: boolean
    runEvery: number
    configJson: string
    platform: string
  }) => void
}

export function TargetWizardPanel({
  mode,
  initialUrl = '',
  onCreated,
  onApplySuggestion,
}: TargetWizardPanelProps) {
  const [url, setUrl] = useState(initialUrl)
  const [name, setName] = useState('')
  const [targetType, setTargetType] = useState('html')
  const [enabled, setEnabled] = useState(true)
  const [runEvery, setRunEvery] = useState(120)
  const [configJson, setConfigJson] = useState('')
  const [platform, setPlatform] = useState<string | null>(null)
  const [detected, setDetected] = useState(false)
  const [analyzed, setAnalyzed] = useState(false)
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})
  const [conflictTargetId, setConflictTargetId] = useState<number | null>(null)

  const applySuggestion = (s: WizardSuggestedConfig, plat: string, wasDetected: boolean) => {
    setName(s.name)
    setTargetType(s.target_type || 'html')
    setEnabled(s.enabled ?? true)
    setRunEvery(s.run_every_minutes ?? 120)
    setConfigJson(JSON.stringify(s.config ?? {}, null, 2))
    setPlatform(plat)
    setDetected(wasDetected)
    setAnalyzed(true)
    setConflictTargetId(null)
  }

  const detectM = useMutation({
    mutationFn: () => wizardDetectPlatform(url),
    onSuccess: (data) => {
      if (!data.suggested_config) {
        setBanner({ error: 'No configuration returned for this URL.' })
        return
      }
      applySuggestion(data.suggested_config, data.platform, data.detected)
      setBanner({
        message: data.detected
          ? `Detected ${platformLabel(data.platform)} — review selectors below.`
          : 'No known platform — generic selectors applied. Review and adjust before saving.',
      })
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err, 'Could not analyze URL.') }),
  })

  const createM = useMutation({
    mutationFn: () => {
      const parsed = parseConfigJson(configJson)
      if (!parsed.ok) throw new Error(parsed.message)
      const trimmedUrl = url.trim()
      const trimmedName = name.trim()
      if (!trimmedUrl) throw new Error('URL is required.')
      if (!trimmedName) throw new Error('Name is required.')
      return wizardCreateTarget({
        url: trimmedUrl,
        name: trimmedName,
        target_type: targetType,
        run_every_minutes: runEvery,
        enabled,
        config: parsed.value,
      })
    },
    onSuccess: (data) => {
      setBanner({ message: data.message ?? 'Target created.' })
      if (data.target_id != null) onCreated?.(data.target_id)
    },
    onError: (err) => {
      if (err instanceof WizardConflictError) {
        setConflictTargetId(err.targetId)
        setBanner({ error: err.message })
        return
      }
      setBanner({ error: getApiErrorMessage(err, 'Could not create target.') })
    },
  })

  const onAnalyze = () => {
    setBanner({})
    setConflictTargetId(null)
    const trimmed = url.trim()
    if (!trimmed) {
      setBanner({ error: 'Enter a listing URL to analyze.' })
      return
    }
    detectM.mutate()
  }

  const onApplyToForm = () => {
    setBanner({})
    const parsed = parseConfigJson(configJson)
    if (!parsed.ok) {
      setBanner({ error: parsed.message })
      return
    }
    onApplySuggestion?.({
      name: name.trim(),
      startUrl: url.trim(),
      targetType,
      enabled,
      runEvery,
      configJson,
      platform: platform ?? 'generic',
    })
    setBanner({ message: 'Suggested selectors applied to the form below.' })
  }

  const onCreate = () => {
    setBanner({})
    setConflictTargetId(null)
    createM.mutate()
  }

  const busy = detectM.isPending || createM.isPending

  return (
    <div className="space-y-4 rounded-lg border border-border bg-card p-4">
      <div className="flex flex-wrap items-start justify-between gap-2">
        <div>
          <h3 className="flex items-center gap-2 font-semibold text-foreground">
            <Wand2 className="size-4 text-primary" aria-hidden />
            {mode === 'create' ? 'Set up a new site' : 'Re-check this site'}
          </h3>
          <p className="mt-1 text-sm text-muted-foreground">
            {mode === 'create'
              ? "Paste a link to the page — we'll detect the site and set it up automatically."
              : "Re-check the URL to refresh this site's settings."}
          </p>
        </div>
        {analyzed && platform ? (
          <StatusBadge status={detected ? platformLabel(platform) : 'Generic'} />
        ) : null}
      </div>

      <AlertBanner message={banner.message} error={banner.error} />

      {conflictTargetId != null ? (
        <p className="text-sm">
          <Link className="text-primary underline-offset-4 hover:underline" to={`/targets/${conflictTargetId}`}>
            Open existing target #{conflictTargetId}
          </Link>
        </p>
      ) : null}

      <div className="grid gap-2">
        <label className="text-sm font-medium text-foreground" htmlFor="wizard-url">
          Page URL
        </label>
        <div className="flex flex-wrap gap-2">
          <Input
            id="wizard-url"
            type="url"
            className="min-w-[240px] flex-1"
            placeholder="https://www.eventbrite.com/d/..."
            value={url}
            onChange={(e) => {
              setUrl(e.target.value)
              setAnalyzed(false)
            }}
            disabled={busy}
          />
          <Button type="button" variant="secondary" disabled={busy} onClick={onAnalyze} className="gap-2">
            {detectM.isPending ? (
              <>
                <Loader2 className="size-4 animate-spin" aria-hidden />
                Analyzing…
              </>
            ) : (
              <>
                <Sparkles className="size-4" aria-hidden />
                Check URL
              </>
            )}
          </Button>
        </div>
      </div>

      {analyzed ? (
        <div className="space-y-4 border-t border-border pt-4">
          <div className="grid gap-2">
            <label className="text-sm font-medium text-foreground" htmlFor="wizard-name">
              Target name
            </label>
            <Input id="wizard-name" value={name} onChange={(e) => setName(e.target.value)} disabled={busy} />
          </div>

          <div className="grid gap-2 sm:grid-cols-2 sm:gap-4">
            <div className="grid gap-2">
              <label className="text-sm font-medium text-foreground" htmlFor="wizard-type">
                Scrape engine
              </label>
              <Select
                id="wizard-type"
                value={targetType}
                onChange={(e) => setTargetType(e.target.value)}
                disabled={busy}
              >
                <option value="html">{targetTypeLabelLong('html')}</option>
                <option value="playwright">{targetTypeLabelLong('playwright')}</option>
              </Select>
            </div>
            <div className="grid gap-2">
              <label className="text-sm font-medium text-foreground" htmlFor="wizard-interval">
                Run every (minutes)
              </label>
              <Input
                id="wizard-interval"
                type="number"
                min={1}
                value={runEvery}
                onChange={(e) => setRunEvery(Number(e.target.value))}
                disabled={busy}
              />
            </div>
          </div>

          <label className="flex items-center gap-2 text-sm">
            <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} disabled={busy} />
            Enabled for scheduled scrapes
          </label>

          <div className="grid gap-2">
            <label className="text-sm font-medium text-foreground" htmlFor="wizard-config">
              Detected configuration (JSON)
            </label>
            <textarea
              id="wizard-config"
              className="min-h-[200px] w-full rounded-md border border-border bg-background p-3 font-mono text-xs leading-relaxed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
              value={configJson}
              onChange={(e) => setConfigJson(e.target.value)}
              spellCheck={false}
              disabled={busy}
            />
            <p className="text-xs text-muted-foreground">
              Tweaks here are merged with the auto-detected base config when you create the target.
            </p>
          </div>

          <div className="flex flex-wrap gap-2">
            {mode === 'create' ? (
              <Button type="button" disabled={busy} onClick={onCreate} className="gap-2">
                {createM.isPending ? (
                  <>
                    <Loader2 className="size-4 animate-spin" aria-hidden />
                    Creating…
                  </>
                ) : (
                  'Create target with wizard'
                )}
              </Button>
            ) : (
              <Button type="button" disabled={busy} onClick={onApplyToForm}>
                Apply to form
              </Button>
            )}
            <Button type="button" variant="outline" disabled={busy} onClick={onAnalyze}>
              Re-analyze
            </Button>
          </div>
        </div>
      ) : null}
    </div>
  )
}
