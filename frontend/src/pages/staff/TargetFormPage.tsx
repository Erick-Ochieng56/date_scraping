import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useNavigate, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import {
  createTarget,
  getTarget,
  triggerTarget,
  updateTarget,
  type TargetWritePayload,
} from '@/lib/api/dashboard'

/** Matches `scraper.services.runner.run_target` — adjust selectors for your listing page. */
const DEFAULT_CONFIG_JSON = `{
  "item_selector": "article, .listing-item, tr",
  "fields": {
    "title": "h2 a, h3 a, h2, h3",
    "url": { "selector": "a", "attr": "href" }
  },
  "max_pages": 1
}`

function parseConfigJson(raw: string): { ok: true; value: Record<string, unknown> } | { ok: false; message: string } {
  try {
    const v = JSON.parse(raw) as unknown
    if (v === null || typeof v !== 'object' || Array.isArray(v)) {
      return { ok: false, message: 'Config must be a JSON object.' }
    }
    return { ok: true, value: v as Record<string, unknown> }
  } catch {
    return { ok: false, message: 'Invalid JSON in configuration.' }
  }
}

function targetTypeLabel(v: string) {
  if (v === 'html') return 'HTML (requests)'
  if (v === 'playwright') return 'Playwright (browser)'
  return v
}

export function TargetFormPage() {
  const { targetId: targetIdParam } = useParams<{ targetId: string }>()
  const navigate = useNavigate()
  const qc = useQueryClient()
  const isNew = targetIdParam === 'new'
  const numericId = useMemo(() => {
    if (isNew || !targetIdParam) return null
    const n = Number(targetIdParam)
    return Number.isFinite(n) ? n : null
  }, [isNew, targetIdParam])

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
  const [configJson, setConfigJson] = useState(DEFAULT_CONFIG_JSON)
  const [localError, setLocalError] = useState<string | null>(null)
  const [actionMessage, setActionMessage] = useState<string | null>(null)

  useEffect(() => {
    if (!detailQ.data) return
    const t = detailQ.data
    setName(t.name)
    setStartUrl(t.start_url)
    setTargetType(t.target_type)
    setEnabled(t.enabled)
    setRunEvery(t.run_every_minutes)
    const hasConfig = t.config && typeof t.config === 'object' && Object.keys(t.config).length > 0
    setConfigJson(hasConfig ? JSON.stringify(t.config, null, 2) : DEFAULT_CONFIG_JSON)
  }, [detailQ.data])

  const buildPayload = (): TargetWritePayload | null => {
    setLocalError(null)
    const trimmedName = name.trim()
    if (!trimmedName) {
      setLocalError('Name is required.')
      return null
    }
    const trimmedUrl = startUrl.trim()
    if (!trimmedUrl) {
      setLocalError('Start URL is required.')
      return null
    }
    const parsed = parseConfigJson(configJson)
    if (!parsed.ok) {
      setLocalError(parsed.message)
      return null
    }
    const itemSel = parsed.value.item_selector ?? parsed.value.items_selector
    if (!itemSel || typeof itemSel !== 'string') {
      setLocalError('Config must include item_selector (CSS) for each row on the listing page.')
      return null
    }
    const fields = parsed.value.fields
    if (!fields || typeof fields !== 'object' || Array.isArray(fields)) {
      setLocalError('Config must include a fields object (field name → selector or { selector, attr }).')
      return null
    }
    return {
      name: trimmedName,
      enabled,
      target_type: targetType,
      start_url: trimmedUrl,
      run_every_minutes: Math.max(1, Math.floor(runEvery) || 60),
      config: parsed.value,
    }
  }

  const saveNewM = useMutation({
    mutationFn: createTarget,
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ['targets'] })
      setActionMessage('Target created. You can run a scrape below.')
      navigate(`/targets/${data.id}`, { replace: true })
    },
    onError: (err: unknown) => {
      const ax = err as { response?: { data?: unknown } }
      setLocalError(formatApiError(ax.response?.data))
    },
  })

  const saveM = useMutation({
    mutationFn: (payload: Partial<TargetWritePayload>) => updateTarget(numericId!, payload),
    onSuccess: () => {
      void qc.invalidateQueries({ queryKey: ['targets'] })
      void qc.invalidateQueries({ queryKey: ['target', numericId] })
      setActionMessage('Saved.')
    },
    onError: (err: unknown) => {
      const ax = err as { response?: { data?: unknown } }
      setLocalError(formatApiError(ax.response?.data))
    },
  })

  const scrapeM = useMutation({
    mutationFn: () => triggerTarget(numericId!),
    onSuccess: (data) => {
      void qc.invalidateQueries({ queryKey: ['targets'] })
      void qc.invalidateQueries({ queryKey: ['scrape-runs'] })
      void qc.invalidateQueries({ queryKey: ['target', numericId] })
      setActionMessage(data.message ?? 'Scrape queued.')
    },
    onError: (err: unknown) => {
      const ax = err as { response?: { data?: unknown } }
      setLocalError(formatApiError(ax.response?.data))
    },
  })

  const onSave = () => {
    setActionMessage(null)
    const payload = buildPayload()
    if (!payload) return
    if (isNew || numericId == null) {
      saveNewM.mutate(payload)
      return
    }
    saveM.mutate(payload)
  }

  const onScrape = () => {
    setActionMessage(null)
    setLocalError(null)
    if (numericId == null) return
    const ok = window.confirm(
      'Start a scrape now for this target? A new scrape run will appear under Scrape runs.'
    )
    if (ok) scrapeM.mutate()
  }

  if (!isNew && numericId == null) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">Invalid target link.</p>
        <Button variant="outline" asChild>
          <Link to="/targets">Back to targets</Link>
        </Button>
      </div>
    )
  }

  const saving = saveNewM.isPending || saveM.isPending
  const busy = saving || scrapeM.isPending

  return (
    <div className="mx-auto max-w-3xl space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-foreground">{isNew ? 'New scrape target' : 'Edit target'}</h2>
          <p className="mt-1 text-sm text-muted-foreground">
            Set the listing URL, CSS selectors in <code className="rounded bg-muted px-1">config</code>, then save and
            run a manual scrape. Scheduled runs use the same configuration.
          </p>
        </div>
        <Button variant="outline" asChild>
          <Link to="/targets">← All targets</Link>
        </Button>
      </div>

      {!isNew && detailQ.isLoading ? <p className="text-sm text-muted-foreground">Loading target...</p> : null}
      {!isNew && detailQ.isError ? (
        <p className="text-sm text-destructive">Could not load this target. It may have been removed.</p>
      ) : null}

      {(localError || actionMessage) && (
        <div className="space-y-1 rounded-md border border-border bg-muted/40 px-3 py-2 text-sm">
          {localError ? <p className="text-destructive">{localError}</p> : null}
          {actionMessage && !localError ? <p className="text-foreground">{actionMessage}</p> : null}
        </div>
      )}

      <div className="space-y-4 rounded-lg border border-border bg-card p-4">
        <div className="grid gap-2">
          <label className="text-sm font-medium text-foreground" htmlFor="tgt-name">
            Name
          </label>
          <input
            id="tgt-name"
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
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
          <input
            id="tgt-url"
            type="url"
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
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
            <select
              id="tgt-type"
              className="h-9 rounded-md border border-border bg-background px-3 text-sm"
              value={targetType}
              onChange={(e) => setTargetType(e.target.value)}
              disabled={busy}
            >
              <option value="html">{targetTypeLabel('html')}</option>
              <option value="playwright">{targetTypeLabel('playwright')}</option>
            </select>
          </div>
          <div className="grid gap-2">
            <label className="text-sm font-medium text-foreground" htmlFor="tgt-interval">
              Run every (minutes)
            </label>
            <input
              id="tgt-interval"
              type="number"
              min={1}
              className="h-9 rounded-md border border-border bg-background px-3 text-sm"
              value={runEvery}
              onChange={(e) => setRunEvery(Number(e.target.value))}
              disabled={busy}
            />
            <p className="text-xs text-muted-foreground">Used by the beat scheduler, not for manual scrapes.</p>
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
            className="min-h-[220px] w-full rounded-md border border-border bg-background p-3 font-mono text-xs leading-relaxed"
            value={configJson}
            onChange={(e) => setConfigJson(e.target.value)}
            spellCheck={false}
            disabled={busy}
          />
          <p className="text-xs text-muted-foreground">
            Required: <code className="rounded bg-muted px-1">item_selector</code> and{' '}
            <code className="rounded bg-muted px-1">fields</code>. Optional:{' '}
            <code className="rounded bg-muted px-1">next_page_selector</code>,{' '}
            <code className="rounded bg-muted px-1">max_pages</code>, Playwright options.
          </p>
        </div>

        <div className="flex flex-wrap gap-2 border-t border-border pt-4">
          <Button type="button" disabled={busy} onClick={onSave}>
            {saving ? 'Saving...' : isNew ? 'Create target' : 'Save changes'}
          </Button>
          {!isNew && numericId != null ? (
            <>
              <Button type="button" variant="secondary" disabled={busy} onClick={onScrape}>
                {scrapeM.isPending ? 'Queueing scrape...' : 'Scrape now'}
              </Button>
              <Button variant="outline" asChild>
                <Link to={`/runs?target_id=${numericId}`}>View scrape runs</Link>
              </Button>
            </>
          ) : null}
        </div>
      </div>
    </div>
  )
}

function formatApiError(data: unknown): string {
  if (data == null) return 'Request failed.'
  if (typeof data === 'string') return data
  if (typeof data === 'object' && data !== null && 'error' in data && typeof (data as { error: string }).error === 'string') {
    return (data as { error: string }).error
  }
  if (typeof data === 'object' && data !== null) {
    const parts: string[] = []
    for (const [k, v] of Object.entries(data as Record<string, unknown>)) {
      if (k === 'success') continue
      if (Array.isArray(v)) parts.push(`${k}: ${v.join(', ')}`)
      else if (typeof v === 'string') parts.push(`${k}: ${v}`)
      else parts.push(`${k}: ${JSON.stringify(v)}`)
    }
    if (parts.length) return parts.join(' · ')
  }
  return 'Request failed.'
}
