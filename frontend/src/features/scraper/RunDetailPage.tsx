import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useMemo } from 'react'
import { Link, useParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { getApiErrorMessage } from '@/shared/api/errors'
import { getScrapeRun, retryScrapeRun } from '@/shared/api/scraper'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { KpiCard } from '@/shared/components/KpiCard'
import { PageHeader } from '@/shared/components/PageHeader'
import { RunStatusBadge } from '@/shared/components/RunStatusBadge'
import { SectionEyebrow } from '@/shared/components/SectionEyebrow'
import { TextLink } from '@/shared/components/TextLink'
import { pollIntervalWhenRunning } from '@/shared/hooks/usePollWhen'

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
    const status = runQ.data.status
    if (status === 'running') return 'Running now — this page auto-refreshes every few seconds.'
    if (status === 'success') return 'Completed successfully.'
    if (status === 'failed') return 'Run failed. You can retry below or from the runs list.'
    return runQ.data.status_display || status
  }, [runQ.data])

  if (!runId) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">Invalid run id.</p>
        <Button variant="outline" asChild>
          <Link to="/runs">Back to runs</Link>
        </Button>
      </div>
    )
  }

  const run = runQ.data

  return (
    <div className="space-y-4">
      <PageHeader
        title={`Scrape run #${runId}`}
        description={statusHint}
        actions={
          <div className="flex flex-wrap gap-2">
            {run?.status === 'failed' ? (
              <Button disabled={retryM.isPending} onClick={() => retryM.mutate()}>
                {retryM.isPending ? 'Retrying…' : 'Retry run'}
              </Button>
            ) : null}
            <Button variant="outline" asChild>
              <Link to="/runs">← All runs</Link>
            </Button>
          </div>
        }
      />

      {retryM.isError ? <AlertBanner error={getApiErrorMessage(retryM.error)} /> : null}

      {runQ.isLoading ? <p className="text-sm text-muted-foreground">Loading run…</p> : null}

      {run ? (
        <>
          <section className="space-y-3">
            <SectionEyebrow>Run summary</SectionEyebrow>
            <div className="grid gap-3 md:grid-cols-3">
              <div className="rounded-lg border border-border bg-card p-4">
                <p className="text-[11px] font-semibold uppercase tracking-wide text-tertiary">Status</p>
                <div className="mt-2">
                  <RunStatusBadge status={run.status} display={run.status_display} />
                </div>
                <p className="mt-2 text-xs text-muted-foreground">Target: {run.target_name}</p>
              </div>
              <KpiCard label="Items scraped" value={run.item_count} />
              <KpiCard label="Leads created" value={run.created_leads} />
            </div>
          </section>
          <section className="rounded-lg border border-border bg-card p-4">
            <SectionEyebrow>Timeline</SectionEyebrow>
            <p className="mt-2 text-sm text-muted-foreground">Started: {new Date(run.started_at).toLocaleString()}</p>
            <p className="text-sm text-muted-foreground">
              Finished: {run.finished_at ? new Date(run.finished_at).toLocaleString() : '—'}
            </p>
            {run.error_text ? <p className="mt-3 text-sm text-destructive">{run.error_text}</p> : null}
            <div className="mt-3">
              <TextLink to={`/runs?target_id=${run.target}`}>View all runs for this target</TextLink>
            </div>
          </section>
        </>
      ) : null}
    </div>
  )
}
