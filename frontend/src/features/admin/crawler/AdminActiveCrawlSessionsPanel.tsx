import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { adminKeys } from '@/features/admin/queryKeys'
import { formatDurationMinutes, formatTimeRemaining } from '@/features/crawler/crawlSessionPresets'
import { getApiErrorMessage } from '@/shared/api/errors'
import { listAdminActiveCrawlSessions, stopAdminCrawlSession } from '@/shared/api/admin'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { SectionEyebrow } from '@/shared/components/SectionEyebrow'
import { useState } from 'react'

export function AdminActiveCrawlSessionsPanel() {
  const qc = useQueryClient()
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  const sessionsQ = useQuery({
    queryKey: adminKeys.activeCrawlSessions(),
    queryFn: listAdminActiveCrawlSessions,
    refetchInterval: 10_000,
  })

  const stopM = useMutation({
    mutationFn: (runId: number) => stopAdminCrawlSession(runId),
    onSuccess: () => {
      setBanner({ message: 'Session stopped.' })
      void qc.invalidateQueries({ queryKey: adminKeys.activeCrawlSessions() })
      void qc.invalidateQueries({ queryKey: ['admin', 'crawler'] })
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const sessions = sessionsQ.data ?? []

  return (
    <section className="space-y-3">
      <SectionEyebrow>Active crawl sessions</SectionEyebrow>
      <AlertBanner message={banner.message} error={banner.error} />

      <div className="rounded-lg border border-border bg-card p-4">
        {sessionsQ.isLoading ? (
          <p className="text-sm text-muted-foreground">Loading sessions…</p>
        ) : sessions.length === 0 ? (
          <p className="text-sm text-muted-foreground">No active crawl sessions.</p>
        ) : (
          <ul className="space-y-3">
            {sessions.map((s) => (
              <li
                key={s.id}
                className="flex flex-col gap-2 border-b border-border pb-3 last:border-0 last:pb-0 sm:flex-row sm:items-center sm:justify-between"
              >
                <div className="text-sm">
                  <p className="font-medium text-foreground">
                    Run #{s.id}
                    {s.owner_username ? ` · ${s.owner_username}` : ''}
                    {s.duration_minutes ? ` · ${formatDurationMinutes(s.duration_minutes)}` : ''}
                  </p>
                  <p className="text-muted-foreground">
                    {s.ends_at ? `Ends ${new Date(s.ends_at).toLocaleString()}` : 'Running'}
                    {s.time_remaining_seconds != null
                      ? ` · ${formatTimeRemaining(s.time_remaining_seconds)} left`
                      : null}
                    {s.cycles_completed != null ? ` · ${s.cycles_completed} cycle(s)` : null}
                  </p>
                  <p className="text-xs text-tertiary">
                    {s.domains_queued} domains · {s.prospects_created} prospects
                  </p>
                </div>
                <div className="flex flex-wrap gap-2">
                  <Button size="sm" variant="outline" asChild>
                    <Link to={`/admin/crawler/runs`}>All runs</Link>
                  </Button>
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={stopM.isPending}
                    onClick={() => {
                      const ok = window.confirm(`Stop crawl session #${s.id}?`)
                      if (ok) stopM.mutate(s.id)
                    }}
                  >
                    Stop
                  </Button>
                </div>
              </li>
            ))}
          </ul>
        )}
      </div>
    </section>
  )
}
