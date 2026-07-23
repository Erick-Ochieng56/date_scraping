import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { TargetWizardPanel } from '@/features/scraper/TargetWizardPanel'
import {
  buildTargetPayload,
  DEFAULT_TARGET_CONFIG_JSON,
  targetTypeLabelLong,
} from '@/features/scraper/utils'
import { getApiErrorMessage } from '@/shared/api/errors'
import { createTarget, getTarget, triggerTarget, updateTarget } from '@/shared/api/scraper'
import type { TargetWritePayload } from '@/shared/api/types'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { Input } from '@/shared/components/Input'
import { PageHeader } from '@/shared/components/PageHeader'
import { Select } from '@/shared/components/Select'

type FormMode = 'wizard' | 'manual'

export function TargetFormPage() {
  const { targetId: targetIdParam } = useParams<{ targetId: string }>()
  const [searchParams] = useSearchParams()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const isNew = targetIdParam === 'new'
  const numericId = useMemo(() => {
    if (isNew || !targetIdParam) return null
    const n = Number(targetIdParam)
    return Number.isFinite(n) ? n : null
  }, [isNew, targetIdParam])

  const initialMode: FormMode = searchParams.get('mode') === 'manual' ? 'manual' : 'wizard'
  const [formMode, setFormMode] = useState<FormMode>(isNew ? initialMode : 'manual')

  const detailQ = useQuery({
    queryKey: ['target', numericId],
    queryFn: () => getTarget(numericId!),
    enabled: numericId != null,
  })

  const [name, setName] = useState('')
  const [startUrl, setStartUrl] = useState('')
  const [targetType, setTargetType] = useState('html')
  const [enabled, setEnabled] = useState(true)
  const [runEvery, setRunEvery] = useState(60)
  const [configJson, setConfigJson] = useState(DEFAULT_TARGET_CONFIG_JSON)
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  useEffect(() => {
    if (!detailQ.data) return
    const t = detailQ.data
    setName(t.name)
    setStartUrl(t.start_url)
    setTargetType(t.target_type)
    setEnabled(t.enabled)
    setRunEvery(t.run_every_minutes)
    const hasConfig = t.config && typeof t.config === 'object' && Object.keys(t.config).length > 0
    setConfigJson(hasConfig ? JSON.stringify(t.config, null, 2) : DEFAULT_TARGET_CONFIG_JSON)
  }, [detailQ.data])

  const setError = (msg: string) => setBanner({ error: msg })

  const buildPayload = (): TargetWritePayload | null =>
    buildTargetPayload({ name, startUrl, targetType, enabled, runEvery, configJson }, setError)

  const saveNewM = useMutation({
    mutationFn: createTarget,
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ['targets'] })
      setBanner({ message: 'Target created. You can run a scrape below.' })
      navigate(`/targets/${data.id}`, { replace: true })
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const saveM = useMutation({
    mutationFn: (payload: Partial<TargetWritePayload>) => updateTarget(numericId!, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['targets'] })
      void qc.invalidateQueries({ queryKey: ['target', numericId] })
      setBanner({ message: 'Saved.' })
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const scrapeM = useMutation({
    mutationFn: () => triggerTarget(numericId!),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ['targets'] })
      void qc.invalidateQueries({ queryKey: ['scrape-runs'] })
      void qc.invalidateQueries({ queryKey: ['target', numericId] })
      setBanner({ message: data.message ?? 'Scrape queued.' })
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const onWizardCreated = (targetId: number) => {
    void qc.invalidateQueries({ queryKey: ['targets'] })
    navigate(`/targets/${targetId}`, { replace: true })
  }

  const onApplySuggestion = (suggestion: {
    name: string
    startUrl: string
    targetType: string
    enabled: boolean
    runEvery: number
    configJson: string
  }) => {
    setName(suggestion.name)
    setStartUrl(suggestion.startUrl)
    setTargetType(suggestion.targetType)
    setEnabled(suggestion.enabled)
    setRunEvery(suggestion.runEvery)
    setConfigJson(suggestion.configJson)
    setFormMode('manual')
  }

  const onSave = () => {
    setBanner({})
    const payload = buildPayload()
    if (!payload) return
    if (isNew || numericId == null) {
      saveNewM.mutate(payload)
      return
    }
    saveM.mutate(payload)
  }

  const onScrape = () => {
    setBanner({})
    if (numericId == null) return
    const ok = window.confirm('Start a scrape now for this target? A new run will appear under Scrape runs.')
    if (ok) scrapeM.mutate()
  }

  if (!isNew && numericId == null) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">Invalid target link.</p>
        <Button variant="outline" asChild>
          <Link to="/targets">Back to sites</Link>
        </Button>
      </div>
    )
  }

  const saving = saveNewM.isPending || saveM.isPending
  const busy = saving || scrapeM.isPending

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <PageHeader
        title={isNew ? 'Add a site to check' : 'Edit site'}
        description={
          isNew
            ? "Paste a URL and we'll set it up automatically, or configure it yourself."
            : "Update this site's settings, or re-check its URL for fresh defaults."
        }
        actions={
          <Button variant="outline" asChild>
            <Link to="/targets">← All sites</Link>
          </Button>
        }
      />

      {isNew ? (
        <div className="flex gap-1 rounded-lg border border-border bg-muted/40 p-1">
          <Button
            type="button"
            size="sm"
            variant={formMode === 'wizard' ? 'default' : 'ghost'}
            onClick={() => setFormMode('wizard')}
          >
            Smart setup
          </Button>
          <Button
            type="button"
            size="sm"
            variant={formMode === 'manual' ? 'default' : 'ghost'}
            onClick={() => setFormMode('manual')}
          >
            Manual JSON
          </Button>
        </div>
      ) : null}

      {!isNew && detailQ.isLoading ? <p className="text-sm text-muted-foreground">Loading target…</p> : null}
      {!isNew && detailQ.isError ? (
        <p className="text-sm text-destructive">Could not load this target. It may have been removed.</p>
      ) : null}

      {isNew && formMode === 'wizard' ? (
        <TargetWizardPanel mode="create" onCreated={onWizardCreated} />
      ) : null}

      {!isNew ? (
        <TargetWizardPanel mode="assist" initialUrl={startUrl} onApplySuggestion={onApplySuggestion} />
      ) : null}

      {(isNew && formMode === 'manual') || !isNew ? (
        <>
          <AlertBanner message={banner.message} error={banner.error} />

          <div className="space-y-4 rounded-lg border border-border bg-card p-4">
            <div className="grid gap-2">
              <label className="text-sm font-medium text-foreground" htmlFor="tgt-name">
                Name
              </label>
              <Input
                id="tgt-name"
                value={name}
                onChange={(e) => setName(e.target.value)}
                placeholder="e.g. City events directory"
                disabled={busy}
              />
              <p className="text-xs text-muted-foreground">Unique label for this source (shown in runs and lists).</p>
            </div>

            <div className="grid gap-2">
              <label className="text-sm font-medium text-foreground" htmlFor="tgt-url">
                Start URL
              </label>
              <Input
                id="tgt-url"
                type="url"
                value={startUrl}
                onChange={(e) => setStartUrl(e.target.value)}
                placeholder="https://example.com/events"
                disabled={busy}
              />
            </div>

            <div className="grid gap-2 sm:grid-cols-2 sm:gap-4">
              <div className="grid gap-2">
                <label className="text-sm font-medium text-foreground" htmlFor="tgt-type">
                  Scrape engine
                </label>
                <Select
                  id="tgt-type"
                  value={targetType}
                  onChange={(e) => setTargetType(e.target.value)}
                  disabled={busy}
                >
                  <option value="html">{targetTypeLabelLong('html')}</option>
                  <option value="playwright">{targetTypeLabelLong('playwright')}</option>
                </Select>
              </div>
              <div className="grid gap-2">
                <label className="text-sm font-medium text-foreground" htmlFor="tgt-interval">
                  Check every (minutes)
                </label>
                <Input
                  id="tgt-interval"
                  type="number"
                  min={1}
                  value={runEvery}
                  onChange={(e) => setRunEvery(Number(e.target.value))}
                  disabled={busy}
                />
                <p className="text-xs text-muted-foreground">
                  How often we check automatically — doesn't affect checks you run yourself.
                </p>
              </div>
            </div>

            <label className="flex items-center gap-2 text-sm">
              <input type="checkbox" checked={enabled} onChange={(e) => setEnabled(e.target.checked)} disabled={busy} />
              Enabled for scheduled scrapes
            </label>

            <div className="grid gap-2">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <label className="text-sm font-medium text-foreground" htmlFor="tgt-config">
                  Configuration (JSON)
                </label>
                {!isNew && detailQ.data?.last_run_at ? (
                  <span className="text-xs text-muted-foreground">
                    Last run: {new Date(detailQ.data.last_run_at).toLocaleString()}
                  </span>
                ) : null}
              </div>
              <textarea
                id="tgt-config"
                className="min-h-[220px] w-full rounded-md border border-border bg-background p-3 font-mono text-xs leading-relaxed focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                value={configJson}
                onChange={(e) => setConfigJson(e.target.value)}
                spellCheck={false}
                disabled={busy}
              />
              <p className="text-xs text-muted-foreground">
                Required: <code className="rounded bg-muted px-1">item_selector</code> and{' '}
                <code className="rounded bg-muted px-1">fields</code>. Use smart setup above to auto-fill these.
              </p>
            </div>

            <div className="flex flex-wrap gap-2 border-t border-border pt-4">
              <Button type="button" disabled={busy} onClick={onSave}>
                {saving ? 'Saving…' : isNew ? 'Create target' : 'Save changes'}
              </Button>
              {!isNew && numericId != null ? (
                <>
                  <Button type="button" variant="secondary" disabled={busy} onClick={onScrape}>
                    {scrapeM.isPending ? 'Queueing scrape…' : 'Scrape now'}
                  </Button>
                  <Button variant="outline" asChild>
                    <Link to={`/runs?target_id=${numericId}`}>View check history</Link>
                  </Button>
                </>
              ) : null}
            </div>
          </div>
        </>
      ) : null}
    </div>
  )
}
