import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { cancelAllRunningCrawls, cancelCrawlRun, listCrawlRuns, triggerCrawler } from '@/lib/api/dashboard'

function triggerLabel(trigger: string) {
  if (trigger === 'scheduled') return 'Scheduled'
  if (trigger === 'manual') return 'Manual'
  return trigger
}

function truncate(s: string, max = 72) {
  if (!s) return ''
  return s.length <= max ? s : `${s.slice(0, max)}…`
}

export function CrawlerRunsPage() {
  const qc = useQueryClient()
  const [statusFilter, setStatusFilter] = useState('')
  const [triggerFilter, setTriggerFilter] = useState('')

  const runsQ = useQuery({
    queryKey: ['crawler-runs-page', statusFilter, triggerFilter],
    queryFn: () =>
      listCrawlRuns({
        page_size: 50,
        status: statusFilter || undefined,
        trigger: triggerFilter || undefined,
      }),
    refetchInterval: statusFilter === 'running' || !statusFilter ? 5000 : 15000,
  })

  const triggerM = useMutation({
    mutationFn: triggerCrawler,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['crawler-runs-page'] }),
  })
  const cancelAllM = useMutation({
    mutationFn: cancelAllRunningCrawls,
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['crawler-runs-page'] }),
  })
  const cancelOneM = useMutation({
    mutationFn: (runId: number) => cancelCrawlRun(runId),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['crawler-runs-page'] }),
  })

  const total = runsQ.data?.total ?? 0

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-foreground">Crawl runs</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Discovery and domain crawl jobs only — separate from manual scraper runs under <strong>Scraper</strong>.
          </p>
          <p className="mt-1 text-sm text-muted-foreground">
            Showing {runsQ.data?.items?.length ?? 0} of {total} run(s) in this view.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void qc.invalidateQueries({ queryKey: ['crawler-runs-page'] })}>
            Refresh
          </Button>
          <Button
            variant="outline"
            disabled={cancelAllM.isPending}
            onClick={() => {
              const ok = window.confirm(
                'Cancel all currently running crawls? This will stop active processing for all running crawl runs.'
              )
              if (ok) cancelAllM.mutate()
            }}
          >
            {cancelAllM.isPending ? 'Cancelling...' : 'Cancel all running'}
          </Button>
          <Button disabled={triggerM.isPending} onClick={() => triggerM.mutate()}>
            {triggerM.isPending ? 'Queueing...' : 'Trigger crawler'}
          </Button>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
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
        <select
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          value={triggerFilter}
          onChange={(e) => setTriggerFilter(e.target.value)}
        >
          <option value="">All triggers</option>
          <option value="manual">Manual</option>
          <option value="scheduled">Scheduled</option>
        </select>
      </div>

      <div className="overflow-auto rounded-lg border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-3 py-2 text-left">Run</th>
              <th className="px-3 py-2 text-left">Trigger</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-left">Domains</th>
              <th className="px-3 py-2 text-left">Prospects</th>
              <th className="px-3 py-2 text-left">Started</th>
              <th className="px-3 py-2 text-left">Finished</th>
              <th className="px-3 py-2 text-left">Last error</th>
              <th className="px-3 py-2 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {(runsQ.data?.items ?? []).map((r) => (
              <tr key={r.id} className="border-t border-border align-top">
                <td className="px-3 py-2 font-medium">#{r.id}</td>
                <td className="px-3 py-2">{triggerLabel(r.trigger)}</td>
                <td className="px-3 py-2">{r.status_display || r.status}</td>
                <td className="px-3 py-2">{r.domains_queued}</td>
                <td className="px-3 py-2">
                  +{r.prospects_created} / upd {r.prospects_updated}
                </td>
                <td className="px-3 py-2 whitespace-nowrap">{new Date(r.started_at).toLocaleString()}</td>
                <td className="px-3 py-2 whitespace-nowrap">
                  {r.finished_at ? new Date(r.finished_at).toLocaleString() : '—'}
                </td>
                <td className="max-w-[220px] px-3 py-2 text-muted-foreground" title={r.error_text || undefined}>
                  {r.error_text ? truncate(r.error_text) : '—'}
                </td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" asChild>
                      <Link to={`/crawler/runs/${r.id}`}>Open details</Link>
                    </Button>
                    {r.status === 'running' ? (
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={cancelOneM.isPending}
                        onClick={() => {
                          const ok = window.confirm(`Cancel crawl run #${r.id}? In-flight domain tasks will stop shortly.`)
                          if (ok) cancelOneM.mutate(r.id)
                        }}
                      >
                        Cancel run
                      </Button>
                    ) : null}
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {runsQ.isLoading ? <p className="text-sm text-muted-foreground">Loading crawl runs...</p> : null}
    </div>
  )
}
