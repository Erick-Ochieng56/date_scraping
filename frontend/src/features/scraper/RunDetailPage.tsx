import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { getApiErrorMessage } from '@/shared/api/errors'
import { getScrapeRun, retryScrapeRun } from '@/shared/api/scraper'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { PageHeader } from '@/shared/components/PageHeader'
import { RunStatusBadge } from '@/shared/components/RunStatusBadge'
import { pollIntervalWhenRunning } from '@/shared/hooks/usePollWhen'
import { summarizeScrapeRun } from '@/shared/utils/runSummary'

export function RunDetailPage() {
  const params = useParams()
  const qc = useQueryClient()
  const runId = Number(params.runId)

  const runQ = useQuery({
    queryKey: ['scrape-run', runId],
    queryFn: () => getScrapeRun(runId),
    enabled: Number.isFinite(runId) && runId > 0,
    refetchInterval: (q) => pollIntervalWhenRunning(q.state.data?.status, undefined, 4000),
  })

  const retryM = useMutation({
    mutationFn: () => retryScrapeRun(runId),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['scrape-run', runId] }),
  })

  const statusHint = useMemo(() => {
    if (!runQ.data) return ''
    return summarizeScrapeRun(runQ.data)
  }, [runQ.data])

  if (!runId) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">This check could not be found.</p>
        <Button variant="outline" asChild>
          <Link to="/runs">Back to check history</Link>
        </Button>
      </div>
    )
  }

  const run = runQ.data

  return (
    <div className="space-y-4">
      <PageHeader
        title={`Site check #${runId}`}
        description={statusHint}
        actions={
          <div className="flex flex-wrap gap-2">
            {run?.status === 'failed' ? (
              <Button disabled={retryM.isPending} onClick={() => retryM.mutate()}>
                {retryM.isPending ? 'Retrying…' : 'Try again'}
              </Button>
            ) : null}
            <Button variant="outline" asChild>
              <Link to="/runs">← All checks</Link>
            </Button>
          </div>
        }
      />

      {retryM.isError ? <AlertBanner error={getApiErrorMessage(retryM.error)} /> : null}

      {runQ.isError ? <AlertBanner error={getApiErrorMessage(runQ.error, 'Failed to load this check.')} /> : null}

      {runQ.isLoading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}

      {run ? (
        <div className="grid gap-3 md:grid-cols-3">
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Status</p>
            <div className="mt-1">
              <RunStatusBadge status={run.status} display={run.status_display} />
            </div>
            <p className="mt-2 text-xs text-muted-foreground">Site: {run.target_name}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Listings found</p>
            <p className="text-lg font-semibold">{run.item_count}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Prospects</p>
            <p className="text-lg font-semibold">
              {run.created_leads} new · {run.updated_leads} updated
            </p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4 md:col-span-3">
            <p className="text-sm font-medium text-foreground">Timeline</p>
            <p className="mt-2 text-sm">Started: {new Date(run.started_at).toLocaleString()}</p>
            <p className="text-sm">
              Finished: {run.finished_at ? new Date(run.finished_at).toLocaleString() : '—'}
            </p>
            {run.error_text ? <p className="mt-3 text-sm text-destructive">{run.error_text}</p> : null}
            <div className="mt-3">
              <Button variant="link" className="h-auto p-0" asChild>
                <Link to={`/runs?target_id=${run.target}`}>View all checks for this site</Link>
              </Button>
            </div>
          </div>
        </div>
      ) : null}
    </div>
  )
}
