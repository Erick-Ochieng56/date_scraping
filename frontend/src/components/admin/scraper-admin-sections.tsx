import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import { listAdminScrapeRuns, listAdminScraperTargets, retryAdminScrapeRun, triggerAdminScraperTarget } from '@/lib/api/dashboard'

export function ScraperAdminStatsCards() {
  const targetsQ = useQuery({
    queryKey: ['admin-scraper-targets-table'],
    queryFn: () => listAdminScraperTargets({ page_size: 20 }),
  })
  const failedQ = useQuery({
    queryKey: ['admin-scraper-runs-failed'],
    queryFn: () => listAdminScrapeRuns({ page_size: 1, status: 'failed' }),
  })
  const runningQ = useQuery({
    queryKey: ['admin-scraper-runs-running'],
    queryFn: () => listAdminScrapeRuns({ page_size: 1, status: 'running' }),
  })

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">Targets</p>
        <p className="text-2xl font-semibold">{targetsQ.data?.total ?? 0}</p>
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">Failed runs</p>
        <p className="text-2xl font-semibold">{failedQ.data?.total ?? 0}</p>
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">Running runs</p>
        <p className="text-2xl font-semibold">{runningQ.data?.total ?? 0}</p>
      </div>
    </div>
  )
}

export function ScraperAdminTargetsSection({
  onMessage,
}: {
  onMessage?: (msg: string | null, err: string | null) => void
}) {
  const qc = useQueryClient()
  const targetsQ = useQuery({
    queryKey: ['admin-scraper-targets-table'],
    queryFn: () => listAdminScraperTargets({ page_size: 50 }),
  })

  const triggerM = useMutation({
    mutationFn: triggerAdminScraperTarget,
    onSuccess: (d) => {
      onMessage?.(d.message ?? 'Scrape triggered.', null)
      void qc.invalidateQueries({ queryKey: ['admin-scraper-runs-table'] })
      void qc.invalidateQueries({ queryKey: ['admin-scraper-runs-failed'] })
      void qc.invalidateQueries({ queryKey: ['admin-scraper-runs-running'] })
    },
    onError: (e: unknown) => {
      const ax = e as { response?: { data?: { error?: string } } }
      onMessage?.(null, ax.response?.data?.error ?? 'Could not trigger target.')
    },
  })

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="font-semibold text-foreground">Scrape targets (global)</h3>
        <Button variant="outline" size="sm" onClick={() => void qc.invalidateQueries({ queryKey: ['admin-scraper-targets-table'] })}>
          Refresh
        </Button>
      </div>
      <div className="overflow-auto rounded-md border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-3 py-2 text-left">Target</th>
              <th className="px-3 py-2 text-left">Type</th>
              <th className="px-3 py-2 text-left">Enabled</th>
              <th className="px-3 py-2 text-left">Owner</th>
              <th className="px-3 py-2 text-left">Action</th>
            </tr>
          </thead>
          <tbody>
            {(targetsQ.data?.items ?? []).map((t) => (
              <tr key={t.id} className="border-t border-border">
                <td className="px-3 py-2 font-medium">{t.name}</td>
                <td className="px-3 py-2">{t.target_type}</td>
                <td className="px-3 py-2">{t.enabled ? 'Yes' : 'No'}</td>
                <td className="px-3 py-2">{t.owner_id ?? '—'}</td>
                <td className="px-3 py-2">
                  <Button size="sm" variant="outline" disabled={triggerM.isPending} onClick={() => triggerM.mutate(t.id)}>
                    Trigger scrape
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

export function ScraperAdminRunsSection({
  onMessage,
}: {
  onMessage?: (msg: string | null, err: string | null) => void
}) {
  const qc = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('')

  const runsQ = useQuery({
    queryKey: ['admin-scraper-runs-table', statusFilter],
    queryFn: () => listAdminScrapeRuns({ page_size: 40, status: statusFilter || undefined }),
    refetchInterval: 8000,
  })

  const retryM = useMutation({
    mutationFn: retryAdminScrapeRun,
    onSuccess: (d) => {
      onMessage?.(d.message ?? 'Retry queued.', null)
      void qc.invalidateQueries({ queryKey: ['admin-scraper-runs-table'] })
      void qc.invalidateQueries({ queryKey: ['admin-scraper-runs-failed'] })
      void qc.invalidateQueries({ queryKey: ['admin-scraper-runs-running'] })
    },
    onError: (e: unknown) => {
      const ax = e as { response?: { data?: { error?: string } } }
      onMessage?.(null, ax.response?.data?.error ?? 'Could not retry run.')
    },
  })

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-foreground">Scrape runs (global)</h3>
        <select
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="running">Running</option>
          <option value="success">Success</option>
          <option value="failed">Failed</option>
        </select>
      </div>
      <div className="overflow-auto rounded-md border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-3 py-2 text-left">Run</th>
              <th className="px-3 py-2 text-left">Target</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-left">Owner</th>
              <th className="px-3 py-2 text-left">Started</th>
              <th className="px-3 py-2 text-left">Action</th>
            </tr>
          </thead>
          <tbody>
            {(runsQ.data?.items ?? []).map((r) => (
              <tr key={r.id} className="border-t border-border">
                <td className="px-3 py-2 font-medium">#{r.id}</td>
                <td className="px-3 py-2">{r.target_name}</td>
                <td className="px-3 py-2">{r.status_display}</td>
                <td className="px-3 py-2">{r.owner_id ?? '—'}</td>
                <td className="px-3 py-2 whitespace-nowrap">{r.started_at ? new Date(r.started_at).toLocaleString() : '—'}</td>
                <td className="px-3 py-2">
                  {r.status === 'failed' ? (
                    <Button size="sm" variant="outline" disabled={retryM.isPending} onClick={() => retryM.mutate(r.id)}>
                      Retry
                    </Button>
                  ) : (
                    <span className="text-xs text-muted-foreground">—</span>
                  )}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
