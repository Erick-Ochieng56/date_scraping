import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  cancelAdminCrawlerRun,
  cancelAllAdminCrawlerRuns,
  listAdminCrawlerDomains,
  listAdminCrawlerRuns,
  listAdminCrawlerSources,
  resetAdminFailedCrawlerDomains,
  triggerAdminCrawlerDomain,
  updateAdminCrawlerSource,
} from '@/lib/api/dashboard'

export function CrawlerAdminStatsCards() {
  const sourcesQ = useQuery({
    queryKey: ['admin-crawler-sources-table'],
    queryFn: () => listAdminCrawlerSources({ page_size: 20 }),
  })
  const runsRunningQ = useQuery({
    queryKey: ['admin-crawler-runs-running'],
    queryFn: () => listAdminCrawlerRuns({ page_size: 1, status: 'running' }),
  })
  const domainsPendingQ = useQuery({
    queryKey: ['admin-crawler-domains-pending'],
    queryFn: () => listAdminCrawlerDomains({ page_size: 1, crawl_status: 'pending' }),
  })

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">Sources</p>
        <p className="text-2xl font-semibold">{sourcesQ.data?.total ?? 0}</p>
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">Running runs</p>
        <p className="text-2xl font-semibold">{runsRunningQ.data?.total ?? 0}</p>
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">Pending domains</p>
        <p className="text-2xl font-semibold">{domainsPendingQ.data?.total ?? 0}</p>
      </div>
    </div>
  )
}

export function CrawlerAdminSourcesSection({
  onMessage,
}: {
  onMessage?: (msg: string | null, err: string | null) => void
}) {
  const qc = useQueryClient()
  const sourcesQ = useQuery({
    queryKey: ['admin-crawler-sources-table'],
    queryFn: () => listAdminCrawlerSources({ page_size: 50 }),
  })

  const sourceM = useMutation({
    mutationFn: ({ sourceId, enabled }: { sourceId: number; enabled: boolean }) =>
      updateAdminCrawlerSource(sourceId, { enabled }),
    onSuccess: () => {
      onMessage?.('Source updated.', null)
      void qc.invalidateQueries({ queryKey: ['admin-crawler-sources-table'] })
    },
    onError: (e: unknown) => {
      const ax = e as { response?: { data?: { error?: string } } }
      onMessage?.(null, ax.response?.data?.error ?? 'Could not update source.')
    },
  })

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <h3 className="font-semibold text-foreground">Crawl sources (global)</h3>
        <Button variant="outline" size="sm" onClick={() => void qc.invalidateQueries({ queryKey: ['admin-crawler-sources-table'] })}>
          Refresh
        </Button>
      </div>
      <div className="overflow-auto rounded-md border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-3 py-2 text-left">Source</th>
              <th className="px-3 py-2 text-left">Type</th>
              <th className="px-3 py-2 text-left">Priority</th>
              <th className="px-3 py-2 text-left">Enabled</th>
              <th className="px-3 py-2 text-left">Owner</th>
              <th className="px-3 py-2 text-left">Action</th>
            </tr>
          </thead>
          <tbody>
            {(sourcesQ.data?.items ?? []).map((s) => (
              <tr key={s.id} className="border-t border-border">
                <td className="px-3 py-2 font-medium">{s.name}</td>
                <td className="px-3 py-2">{s.source_type}</td>
                <td className="px-3 py-2">{s.priority}</td>
                <td className="px-3 py-2">{s.enabled ? 'Yes' : 'No'}</td>
                <td className="px-3 py-2">{s.owner_id ?? '—'}</td>
                <td className="px-3 py-2">
                  <Button
                    size="sm"
                    variant="outline"
                    disabled={sourceM.isPending}
                    onClick={() => sourceM.mutate({ sourceId: s.id, enabled: !s.enabled })}
                  >
                    {s.enabled ? 'Disable' : 'Enable'}
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

export function CrawlerAdminDomainsSection({
  onMessage,
}: {
  onMessage?: (msg: string | null, err: string | null) => void
}) {
  const qc = useQueryClient()
  const [domainStatus, setDomainStatus] = useState('')

  const domainsQ = useQuery({
    queryKey: ['admin-crawler-domains-table', domainStatus],
    queryFn: () => listAdminCrawlerDomains({ page_size: 40, crawl_status: domainStatus || undefined }),
    refetchInterval: 8000,
  })

  const triggerDomainM = useMutation({
    mutationFn: triggerAdminCrawlerDomain,
    onSuccess: (d) => {
      onMessage?.(`Domain queued. Run #${d.run_id}.`, null)
      void qc.invalidateQueries({ queryKey: ['admin-crawler-runs-table'] })
      void qc.invalidateQueries({ queryKey: ['admin-crawler-runs-running'] })
      void qc.invalidateQueries({ queryKey: ['admin-crawler-domains-table'] })
    },
    onError: (e: unknown) => {
      const ax = e as { response?: { data?: { error?: string } } }
      onMessage?.(null, ax.response?.data?.error ?? 'Could not trigger domain crawl.')
    },
  })

  const resetFailedM = useMutation({
    mutationFn: () => resetAdminFailedCrawlerDomains(),
    onSuccess: (d) => {
      onMessage?.(`Reset ${d.count} failed domain(s) to pending.`, null)
      void qc.invalidateQueries({ queryKey: ['admin-crawler-domains-table'] })
      void qc.invalidateQueries({ queryKey: ['admin-crawler-domains-pending'] })
    },
    onError: (e: unknown) => {
      const ax = e as { response?: { data?: { error?: string } } }
      onMessage?.(null, ax.response?.data?.error ?? 'Could not reset failed domains.')
    },
  })

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-foreground">Domain queue (global)</h3>
        <div className="flex items-center gap-2">
          <select
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
            value={domainStatus}
            onChange={(e) => setDomainStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            <option value="pending">Pending</option>
            <option value="completed">Completed</option>
            <option value="failed">Failed</option>
          </select>
          <Button variant="outline" size="sm" disabled={resetFailedM.isPending} onClick={() => resetFailedM.mutate()}>
            Reset failed
          </Button>
        </div>
      </div>
      <div className="overflow-auto rounded-md border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-3 py-2 text-left">Domain</th>
              <th className="px-3 py-2 text-left">Discovery URL</th>
              <th className="px-3 py-2 text-left">Source</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-left">Attempts</th>
              <th className="px-3 py-2 text-left">Owner</th>
              <th className="px-3 py-2 text-left">Action</th>
            </tr>
          </thead>
          <tbody>
            {(domainsQ.data?.items ?? []).map((d) => (
              <tr key={d.id} className="border-t border-border">
                <td className="px-3 py-2 font-medium">{d.domain}</td>
                <td className="max-w-[14rem] truncate px-3 py-2 text-xs text-muted-foreground">
                  {d.source_url ? (
                    <a className="text-primary underline-offset-2 hover:underline" href={d.source_url} target="_blank" rel="noreferrer">
                      {d.source_url}
                    </a>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="px-3 py-2">{d.source_name || '—'}</td>
                <td className="px-3 py-2">{d.crawl_status}</td>
                <td className="px-3 py-2">{d.crawl_attempts}</td>
                <td className="px-3 py-2">{d.owner_id ?? '—'}</td>
                <td className="px-3 py-2">
                  <Button size="sm" variant="outline" disabled={triggerDomainM.isPending} onClick={() => triggerDomainM.mutate(d.id)}>
                    Crawl now
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

export function CrawlerAdminRunsSection({
  onMessage,
}: {
  onMessage?: (msg: string | null, err: string | null) => void
}) {
  const qc = useQueryClient()
  const [runStatus, setRunStatus] = useState('')

  const runsQ = useQuery({
    queryKey: ['admin-crawler-runs-table', runStatus],
    queryFn: () => listAdminCrawlerRuns({ page_size: 40, status: runStatus || undefined }),
    refetchInterval: 8000,
  })
  const runsFailedQ = useQuery({
    queryKey: ['admin-crawler-runs-failed'],
    queryFn: () => listAdminCrawlerRuns({ page_size: 1, status: 'failed' }),
  })

  const cancelRunM = useMutation({
    mutationFn: cancelAdminCrawlerRun,
    onSuccess: (d) => {
      onMessage?.(d.message ?? 'Run cancelled.', null)
      void qc.invalidateQueries({ queryKey: ['admin-crawler-runs-table'] })
      void qc.invalidateQueries({ queryKey: ['admin-crawler-runs-failed'] })
      void qc.invalidateQueries({ queryKey: ['admin-crawler-runs-running'] })
    },
    onError: (e: unknown) => {
      const ax = e as { response?: { data?: { error?: string } } }
      onMessage?.(null, ax.response?.data?.error ?? 'Could not cancel run.')
    },
  })

  const cancelAllM = useMutation({
    mutationFn: cancelAllAdminCrawlerRuns,
    onSuccess: (d) => {
      onMessage?.(`Cancelled ${d.cancelled} running run(s).`, null)
      void qc.invalidateQueries({ queryKey: ['admin-crawler-runs-table'] })
      void qc.invalidateQueries({ queryKey: ['admin-crawler-runs-failed'] })
      void qc.invalidateQueries({ queryKey: ['admin-crawler-runs-running'] })
    },
    onError: (e: unknown) => {
      const ax = e as { response?: { data?: { error?: string } } }
      onMessage?.(null, ax.response?.data?.error ?? 'Could not cancel running runs.')
    },
  })

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
        <h3 className="font-semibold text-foreground">Crawl runs (global)</h3>
        <div className="flex flex-wrap items-center gap-2">
          <select
            className="h-9 rounded-md border border-border bg-background px-3 text-sm"
            value={runStatus}
            onChange={(e) => setRunStatus(e.target.value)}
          >
            <option value="">All statuses</option>
            <option value="running">Running</option>
            <option value="success">Success</option>
            <option value="failed">Failed</option>
          </select>
          <Button variant="outline" size="sm" disabled={cancelAllM.isPending} onClick={() => cancelAllM.mutate()}>
            Cancel all running
          </Button>
        </div>
      </div>
      <div className="overflow-auto rounded-md border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-3 py-2 text-left">Run</th>
              <th className="px-3 py-2 text-left">Trigger</th>
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
                <td className="px-3 py-2">{r.trigger}</td>
                <td className="px-3 py-2">{r.status_display}</td>
                <td className="px-3 py-2">{r.owner_id ?? '—'}</td>
                <td className="px-3 py-2 whitespace-nowrap">{r.started_at ? new Date(r.started_at).toLocaleString() : '—'}</td>
                <td className="px-3 py-2">
                  {r.status === 'running' ? (
                    <Button size="sm" variant="outline" disabled={cancelRunM.isPending} onClick={() => cancelRunM.mutate(r.id)}>
                      Cancel run
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
      <p className="mt-2 text-xs text-muted-foreground">Failed runs (total): {runsFailedQ.data?.total ?? 0}</p>
    </div>
  )
}
