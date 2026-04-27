import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { listScrapeRuns, listTargets, retryScrapeRun, triggerTarget } from '@/lib/api/dashboard'

type RunRow = {
  id: number
  target_id: number
  target_name: string
  status: string
  started_at: string
  finished_at: string | null
  item_count: number
  created_leads: number
  updated_leads: number
}

export function RunsPage() {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const initialTarget = Number(searchParams.get('target_id') || '') || 0
  const [targetId, setTargetId] = useState<number>(initialTarget)
  const [statusFilter, setStatusFilter] = useState<string>('')

  const scrapeQ = useQuery({
    queryKey: ['scrape-runs', targetId, statusFilter],
    queryFn: () =>
      listScrapeRuns({
        page_size: 50,
        target_id: targetId || undefined,
        status: statusFilter || undefined,
      }),
    refetchInterval: 5000,
  })
  const targetsQ = useQuery({
    queryKey: ['targets-run-filter'],
    queryFn: () => listTargets({ page_size: 200 }),
  })

  const retryM = useMutation({
    mutationFn: (runId: number) => retryScrapeRun(runId),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['scrape-runs'] }),
  })
  const triggerTargetM = useMutation({
    mutationFn: (selectedTargetId: number) => triggerTarget(selectedTargetId),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['scrape-runs'] }),
  })
  const rows = useMemo<RunRow[]>(() => {
    return (scrapeQ.data?.items ?? []).map((r) => ({
      id: r.id,
      target_id: r.target,
      target_name: r.target_name,
      status: r.status,
      started_at: r.started_at,
      finished_at: r.finished_at,
      item_count: r.item_count,
      created_leads: r.created_leads,
      updated_leads: r.updated_leads,
    }))
  }, [scrapeQ.data?.items])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-foreground">Scrape runs</h2>
          <p className="text-sm text-muted-foreground">Manual scraper runs for individual targets only.</p>
        </div>
        <div className="flex gap-2">
          <Button
            disabled={!targetId || triggerTargetM.isPending}
            onClick={() => targetId && triggerTargetM.mutate(targetId)}
          >
            {triggerTargetM.isPending ? 'Queueing...' : 'Trigger selected target'}
          </Button>
          <Button variant="outline" onClick={() => void qc.invalidateQueries({ queryKey: ['scrape-runs'] })}>
            Refresh
          </Button>
        </div>
      </div>
      <div className="flex flex-wrap gap-2">
        <select
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          value={targetId}
          onChange={(e) => {
            const next = Number(e.target.value)
            setTargetId(next)
            if (next) setSearchParams({ target_id: String(next) })
            else setSearchParams({})
          }}
        >
          <option value={0}>All targets</option>
          {(targetsQ.data?.items ?? []).map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </select>
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
      <div className="overflow-auto rounded-lg border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-3 py-2 text-left">Run</th>
              <th className="px-3 py-2 text-left">Target</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-left">Items</th>
              <th className="px-3 py-2 text-left">Leads</th>
              <th className="px-3 py-2 text-left">Started</th>
              <th className="px-3 py-2 text-left">Finished</th>
              <th className="px-3 py-2 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {rows.map((row) => (
              <tr key={row.id} className="border-t border-border">
                <td className="px-3 py-2">
                  <Link to={`/runs/${row.id}`}>#{row.id}</Link>
                </td>
                <td className="px-3 py-2">{row.target_name}</td>
                <td className="px-3 py-2">{row.status}</td>
                <td className="px-3 py-2">{row.item_count}</td>
                <td className="px-3 py-2">
                  +{row.created_leads} / upd {row.updated_leads}
                </td>
                <td className="px-3 py-2">{new Date(row.started_at).toLocaleString()}</td>
                <td className="px-3 py-2">{row.finished_at ? new Date(row.finished_at).toLocaleString() : '-'}</td>
                <td className="px-3 py-2">
                  {row.status === 'failed' ? (
                    <Button size="sm" disabled={retryM.isPending} onClick={() => retryM.mutate(row.id)}>
                      Retry
                    </Button>
                  ) : (
                    <span className="text-muted-foreground">-</span>
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

