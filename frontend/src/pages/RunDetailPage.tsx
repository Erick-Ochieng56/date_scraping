import { useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'

import { getScrapeRun } from '@/lib/api/dashboard'

export function RunDetailPage() {
  const params = useParams()
  const runId = Number(params.runId)
  const runQ = useQuery({
    queryKey: ['scrape-run', runId],
    queryFn: () => getScrapeRun(runId),
    enabled: Number.isFinite(runId) && runId > 0,
    refetchInterval: (query) => (query.state.data?.status === 'running' ? 4000 : false),
  })

  const statusText = useMemo(() => {
    if (!runQ.data) return ''
    const status = runQ.data.status
    if (status === 'running') return 'Running now. This page auto-refreshes.'
    if (status === 'success') return 'Completed successfully.'
    if (status === 'failed') return 'Run failed. You can retry from Runs page.'
    return status
  }, [runQ.data])

  if (!runId) return <p>Invalid run id.</p>

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold text-foreground">Run #{runId}</h2>
        <p className="text-sm text-muted-foreground">{statusText}</p>
      </div>
      {runQ.isLoading ? <p>Loading run...</p> : null}
      {runQ.data ? (
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-lg border border-border p-4">
            <p className="text-sm text-muted-foreground">Status</p>
            <p className="text-lg font-semibold">{runQ.data.status_display}</p>
          </div>
          <div className="rounded-lg border border-border p-4">
            <p className="text-sm text-muted-foreground">Items scraped</p>
            <p className="text-lg font-semibold">{runQ.data.item_count}</p>
          </div>
          <div className="rounded-lg border border-border p-4">
            <p className="text-sm text-muted-foreground">Leads</p>
            <p className="text-lg font-semibold">
              +{runQ.data.created_leads} / updated {runQ.data.updated_leads}
            </p>
          </div>
          <div className="rounded-lg border border-border p-4 md:col-span-3">
            <p className="text-sm text-muted-foreground">Timeline</p>
            <p>Started: {new Date(runQ.data.started_at).toLocaleString()}</p>
            <p>Finished: {runQ.data.finished_at ? new Date(runQ.data.finished_at).toLocaleString() : '-'}</p>
            {runQ.data.error_text ? <p className="mt-2 text-destructive">{runQ.data.error_text}</p> : null}
          </div>
        </div>
      ) : null}
    </div>
  )
}

