import { useQuery } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { crawlerKeys } from '@/features/crawler/queryKeys'
import {
  formatDurationMinutes,
  formatTimeRemaining,
} from '@/features/crawler/crawlSessionPresets'
import { getCrawlRun, listCrawlRunDomainResults } from '@/shared/api/crawler'
import type { CrawlRunDomainResult } from '@/shared/api/types'
import { DataTable } from '@/shared/components/DataTable'
import { ListPagination } from '@/shared/components/ListPagination'
import { KpiCard } from '@/shared/components/KpiCard'
import { PageHeader } from '@/shared/components/PageHeader'
import { RunStatusBadge } from '@/shared/components/RunStatusBadge'
import { ScoreBadge } from '@/shared/components/ScoreBadge'
import { SectionEyebrow } from '@/shared/components/SectionEyebrow'
import { TextLink } from '@/shared/components/TextLink'
import { Select } from '@/shared/components/Select'
import { pollIntervalWhenRunning } from '@/shared/hooks/usePollWhen'
import { useServerList } from '@/shared/hooks/useServerList'

export function CrawlerRunDetailPage() {
  const params = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const runId = Number(params.runId)
  const [state, setState] = useState(searchParams.get('state') ?? '')
  const [errorsOnly, setErrorsOnly] = useState(searchParams.get('errors_only') === '1')
  const [, setTick] = useState(0)

  const runQ = useQuery({
    queryKey: crawlerKeys.run(runId),
    queryFn: () => getCrawlRun(runId),
    enabled: Number.isFinite(runId) && runId > 0,
    refetchInterval: (q) => pollIntervalWhenRunning(q.state.data?.status, undefined, 5000),
  })

  useEffect(() => {
    if (runQ.data?.trigger !== 'session' || runQ.data?.status !== 'running') return
    const id = window.setInterval(() => setTick((t) => t + 1), 1000)
    return () => window.clearInterval(id)
  }, [runQ.data?.trigger, runQ.data?.status])

  const domainFilters = useMemo(
    () => ({
      ...(state ? { state } : {}),
      ...(errorsOnly ? { errors_only: true as const } : {}),
    }),
    [state, errorsOnly]
  )

  const { items, total, page, pageSize, hasNext, goNext, goPrev, resetPage, query: domainsQ } = useServerList<
    CrawlRunDomainResult,
    { state?: string; errors_only?: boolean }
  >({
    queryKey: ['crawler', 'run', runId, 'domains'],
    queryFn: (p) =>
      listCrawlRunDomainResults(runId, {
        page: p.page,
        page_size: p.page_size,
        state: p.state,
        errors_only: p.errors_only,
      }),
    pageSize: 50,
    filters: domainFilters,
    enabled: Number.isFinite(runId) && runId > 0,
    refetchInterval: () => (runQ.data?.status === 'running' ? 5000 : false),
  })

  useEffect(() => {
    const sp = new URLSearchParams()
    if (state) sp.set('state', state)
    if (errorsOnly) sp.set('errors_only', '1')
    setSearchParams(sp, { replace: true })
    resetPage()
  }, [state, errorsOnly, setSearchParams, resetPage])

  const columns = useMemo<ColumnDef<CrawlRunDomainResult, unknown>[]>(
    () => [
      { accessorKey: 'domain_name', header: 'Domain' },
      {
        accessorKey: 'state',
        header: 'State',
        cell: ({ row }) => <RunStatusBadge status={row.original.state} />,
      },
      {
        id: 'score',
        header: 'Score',
        cell: ({ row }) => (
          <ScoreBadge score={row.original.score} label={row.original.score_label || undefined} />
        ),
      },
      {
        id: 'prospect',
        header: 'Prospect',
        cell: ({ row }) => {
          const id = row.original.prospect_id
          if (id) {
            return (
              <TextLink to={`/prospects/${id}`}>#{id}</TextLink>
            )
          }
          if (row.original.prospect_created) return 'Created'
          if (row.original.prospect_updated) return 'Updated'
          return '—'
        },
      },
      {
        accessorKey: 'crawl_error',
        header: 'Error',
        cell: ({ row }) => (
          <span className="text-destructive">{row.original.crawl_error || '—'}</span>
        ),
      },
    ],
    []
  )

  if (!runId) {
    return (
      <div className="space-y-4">
        <p className="text-sm text-muted-foreground">Invalid run id.</p>
        <Button variant="outline" asChild>
          <Link to="/crawler/runs">Back to runs</Link>
        </Button>
      </div>
    )
  }

  const run = runQ.data
  const isSession = run?.trigger === 'session'
  const sessionProgress =
    isSession && run?.duration_minutes
      ? Math.min(
          100,
          Math.round(
            ((run.duration_minutes * 60 - (run.time_remaining_seconds ?? 0)) /
              (run.duration_minutes * 60)) *
              100
          )
        )
      : null
  const statusHint =
    run?.status === 'running'
      ? 'Running — this page auto-refreshes while the batch is in progress.'
      : run?.status_display || run?.status || ''

  return (
    <div className="space-y-4">
      <PageHeader
        title={`Crawl run #${runId}`}
        description={statusHint}
        actions={
          <Button variant="outline" asChild>
            <Link to="/crawler/runs">← All runs</Link>
          </Button>
        }
      />

      {run ? (
        <section className="space-y-3">
          <SectionEyebrow>Run summary</SectionEyebrow>
          <div className="grid gap-3 md:grid-cols-4">
            <div className="rounded-lg border border-border bg-card p-4">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-tertiary">Status</p>
              <div className="mt-2">
                <RunStatusBadge status={run.status} display={run.status_display} />
              </div>
            </div>
            <KpiCard label="Domains" value={run.summary?.total_domains ?? run.domains_queued} />
            <KpiCard label="Errors" value={run.summary?.failed_domains ?? 0} />
            <KpiCard label="Prospects created" value={run.summary?.prospects_created ?? run.prospects_created} />
          </div>
          {isSession ? (
            <div className="rounded-lg border border-border bg-card p-4 space-y-3">
              <p className="text-[11px] font-semibold uppercase tracking-wide text-tertiary">Session</p>
              <div className="grid gap-3 sm:grid-cols-3 text-sm">
                <div>
                  <p className="text-muted-foreground">Duration</p>
                  <p className="font-medium">
                    {run.duration_minutes ? formatDurationMinutes(run.duration_minutes) : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">Ends</p>
                  <p className="font-medium">
                    {run.ends_at ? new Date(run.ends_at).toLocaleString() : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">Time remaining</p>
                  <p className="font-medium">
                    {run.status === 'running'
                      ? formatTimeRemaining(run.time_remaining_seconds)
                      : '—'}
                  </p>
                </div>
                <div>
                  <p className="text-muted-foreground">Cycles</p>
                  <p className="font-medium">{run.cycles_completed ?? 0}</p>
                </div>
                <div>
                  <p className="text-muted-foreground">Last cycle</p>
                  <p className="font-medium">
                    {run.last_cycle_at ? new Date(run.last_cycle_at).toLocaleString() : '—'}
                  </p>
                </div>
              </div>
              {sessionProgress != null && run.status === 'running' ? (
                <div className="space-y-1">
                  <div className="h-2 w-full overflow-hidden rounded-full bg-muted">
                    <div
                      className="h-full rounded-full bg-secondary transition-all"
                      style={{ width: `${sessionProgress}%` }}
                    />
                  </div>
                  <p className="text-xs text-muted-foreground">{sessionProgress}% elapsed</p>
                </div>
              ) : null}
            </div>
          ) : null}
        </section>
      ) : null}

      <div className="flex flex-wrap gap-2">
        <Select value={state} onChange={(e) => setState(e.target.value)}>
          <option value="">All states</option>
          <option value="queued">Queued</option>
          <option value="crawled">Crawled</option>
          <option value="analyzed">Analyzed</option>
          <option value="scored">Scored</option>
          <option value="failed">Failed</option>
        </Select>
        <label className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm">
          <input type="checkbox" checked={errorsOnly} onChange={(e) => setErrorsOnly(e.target.checked)} />
          Errors only
        </label>
      </div>

      <DataTable
        columns={columns}
        data={items}
        isLoading={domainsQ.isLoading || runQ.isLoading}
        emptyMessage="No domain results for this run."
        getRowId={(r) => String(r.id)}
      />

      <ListPagination
        page={page}
        pageSize={pageSize}
        total={total}
        hasNext={hasNext}
        onPrev={goPrev}
        onNext={goNext}
        isLoading={domainsQ.isFetching}
      />
    </div>
  )
}
