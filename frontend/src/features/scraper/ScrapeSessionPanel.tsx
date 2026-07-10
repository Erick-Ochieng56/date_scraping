import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Clock, Play, Square } from 'lucide-react'
import { useEffect, useState } from 'react'

import { Button } from '@/components/ui/button'
import { Input } from '@/shared/components/Input'
import {
  CRAWL_SESSION_MAX_MINUTES,
  CRAWL_SESSION_MIN_MINUTES,
  CRAWL_SESSION_PRESETS,
  formatTimeRemaining,
  type CrawlSessionPreset,
} from '@/features/crawler/crawlSessionPresets'
import { getApiErrorMessage } from '@/shared/api/errors'
import { getActiveScrapeSession, startScrapeSession, stopScrapeSession } from '@/shared/api/scraper'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { SectionEyebrow } from '@/shared/components/SectionEyebrow'
import { Select } from '@/shared/components/Select'

type Props = {
  onBanner?: (banner: { message?: string; error?: string }) => void
}

type DurationMode = CrawlSessionPreset | 'custom'

export function ScrapeSessionPanel({ onBanner }: Props) {
  const qc = useQueryClient()
  const [durationMode, setDurationMode] = useState<DurationMode>('6h')
  const [customMinutes, setCustomMinutes] = useState('90')
  const [localBanner, setBanner] = useState<{ message?: string; error?: string }>({})
  const [tick, setTick] = useState(0)

  const activeQ = useQuery({
    queryKey: ['scraper', 'active-session'],
    queryFn: getActiveScrapeSession,
    refetchInterval: 5000,
  })

  const active = activeQ.data

  useEffect(() => {
    if (!active?.is_session_active) return
    const id = window.setInterval(() => setTick((t) => t + 1), 30_000)
    return () => window.clearInterval(id)
  }, [active?.is_session_active])

  const setBannerState = (b: { message?: string; error?: string }) => {
    setBanner(b)
    onBanner?.(b)
  }

  const resolveDurationBody = () => {
    if (durationMode === 'custom') {
      const minutes = Number.parseInt(customMinutes, 10)
      if (!Number.isFinite(minutes)) {
        throw new Error('Enter a valid number of minutes.')
      }
      if (minutes < CRAWL_SESSION_MIN_MINUTES || minutes > CRAWL_SESSION_MAX_MINUTES) {
        throw new Error(`Duration must be between ${CRAWL_SESSION_MIN_MINUTES} and ${CRAWL_SESSION_MAX_MINUTES} minutes.`)
      }
      return { duration_minutes: minutes }
    }
    return { preset: durationMode }
  }

  const startM = useMutation({
    mutationFn: () => startScrapeSession(resolveDurationBody()),
    onSuccess: (data) => {
      setBannerState({ message: data.message ?? 'Scrape session started.' })
      void qc.invalidateQueries({ queryKey: ['scraper', 'active-session'] })
      void qc.invalidateQueries({ queryKey: ['scrape-runs'] })
    },
    onError: (err) => setBannerState({ error: getApiErrorMessage(err) }),
  })

  const stopM = useMutation({
    mutationFn: (sessionId: number) => stopScrapeSession(sessionId),
    onSuccess: () => {
      setBannerState({ message: 'Scrape session stopped.' })
      void qc.invalidateQueries({ queryKey: ['scraper', 'active-session'] })
    },
    onError: (err) => setBannerState({ error: getApiErrorMessage(err) }),
  })

  const remaining = active?.time_remaining_seconds ?? null
  void tick

  return (
    <section className="space-y-3">
      <SectionEyebrow>Scrape session</SectionEyebrow>
      <AlertBanner message={localBanner.message} error={localBanner.error} />

      <div className="rounded-lg border border-border bg-card p-4 space-y-4">
        {active?.is_session_active ? (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
            <div className="space-y-1">
              <p className="text-sm font-medium text-foreground flex items-center gap-2">
                <Clock className="size-4 text-secondary" aria-hidden />
                Active session — #{active.id}
              </p>
              <p className="text-sm text-muted-foreground">
                {active.ends_at
                  ? `Ends ${new Date(active.ends_at).toLocaleString()}`
                  : 'Running'}
                {remaining != null ? ` · ${formatTimeRemaining(remaining)} left` : null}
                {active.cycles_completed != null ? ` · ${active.cycles_completed} cycle(s)` : null}
              </p>
              <p className="text-xs text-tertiary">
                {active.targets_enqueued} target scrape(s) enqueued (due targets per cycle)
              </p>
            </div>
            <Button
              size="sm"
              variant="outline"
              disabled={stopM.isPending}
              onClick={() => {
                const ok = window.confirm('Stop this scrape session early?')
                if (ok) stopM.mutate(active.id)
              }}
            >
              <Square className="size-3.5 mr-1" aria-hidden />
              {stopM.isPending ? 'Stopping…' : 'Stop session'}
            </Button>
          </div>
        ) : (
          <div className="flex flex-col gap-3 sm:flex-row sm:items-end">
            <label className="flex flex-col gap-1 text-sm">
              <span className="text-muted-foreground">Duration</span>
              <Select
                value={durationMode}
                onChange={(e) => setDurationMode(e.target.value as DurationMode)}
                className="min-w-[160px]"
              >
                {CRAWL_SESSION_PRESETS.map((p) => (
                  <option key={p.value} value={p.value}>
                    {p.label}
                  </option>
                ))}
                <option value="custom">Custom (minutes)</option>
              </Select>
            </label>
            {durationMode === 'custom' ? (
              <label className="flex flex-col gap-1 text-sm">
                <span className="text-muted-foreground">Minutes</span>
                <Input
                  type="number"
                  min={CRAWL_SESSION_MIN_MINUTES}
                  max={CRAWL_SESSION_MAX_MINUTES}
                  value={customMinutes}
                  onChange={(e) => setCustomMinutes(e.target.value)}
                  className="w-28"
                />
              </label>
            ) : null}
            <Button
              disabled={startM.isPending}
              onClick={() => {
                try {
                  resolveDurationBody()
                  startM.mutate()
                } catch (err) {
                  setBannerState({
                    error: err instanceof Error ? err.message : 'Invalid duration.',
                  })
                }
              }}
            >
              <Play className="size-3.5 mr-1" aria-hidden />
              {startM.isPending ? 'Starting…' : 'Start session'}
            </Button>
          </div>
        )}

        <p className="text-xs text-muted-foreground border-t border-border pt-3">
          While active, enabled targets are enqueued on their <code className="text-xs">run_every_minutes</code>{' '}
          schedule until the session ends.
        </p>
      </div>
    </section>
  )
}
