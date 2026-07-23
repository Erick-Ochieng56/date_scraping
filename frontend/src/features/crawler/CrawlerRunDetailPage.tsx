import { useQuery } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useEffect, useMemo, useState } from 'react'
import { Link, useParams, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { crawlerKeys } from '@/features/crawler/queryKeys'
import { getApiErrorMessage } from '@/shared/api/errors'
import { getCrawlRun, listCrawlRunDomainResults } from '@/shared/api/crawler'
import type { CrawlRunDomainResult } from '@/shared/api/types'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { DataTable } from '@/shared/components/DataTable'
import { ListPagination } from '@/shared/components/ListPagination'
import { PageHeader } from '@/shared/components/PageHeader'
import { RunStatusBadge } from '@/shared/components/RunStatusBadge'
import { Select } from '@/shared/components/Select'
import { pollIntervalWhenRunning } from '@/shared/hooks/usePollWhen'
import { useServerList } from '@/shared/hooks/useServerList'
import { summarizeCrawlRun } from '@/shared/utils/runSummary'

export function CrawlerRunDetailPage() {
  const params = useParams()
  const [searchParams, setSearchParams] = useSearchParams()
  const runId = Number(params.runId)
  const [state, setState] = useState(searchParams.get('state') ?? '')
  const [errorsOnly, setErrorsOnly] = useState(searchParams.get('errors_only') === '1')

  const runQ = useQuery({
    queryKey: crawlerKeys.run(runId),
    queryFn: () => getCrawlRun(runId),
    enabled: Number.isFinite(runId) && runId > 0,
    refetchInterval: (q) => pollIntervalWhenRunning(q.state.data?.status, undefined, 5000),
  })

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
        cell: ({ row }) =>
          `${row.original.score}${row.original.score_label ? ` (${row.original.score_label})` : ''}`,
      },
      {
        id: 'prospect',
        header: 'Prospect',
        cell: ({ row }) =>
          row.original.prospect_created ? 'Created' : row.original.prospect_updated ? 'Updated' : '—',
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
  const statusHint = run ? summarizeCrawlRun(run) : ''

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

      {runQ.isError ? <AlertBanner error={getApiErrorMessage(runQ.error, 'Failed to load this crawl run.')} /> : null}

      {run ? (
        <div className="grid gap-3 md:grid-cols-4">
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Status</p>
            <div className="mt-1">
              <RunStatusBadge status={run.status} display={run.status_display} />
            </div>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Domains</p>
            <p className="text-lg font-semibold">{run.summary?.total_domains ?? run.domains_queued}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Errors</p>
            <p className="text-lg font-semibold">{run.summary?.failed_domains ?? 0}</p>
          </div>
          <div className="rounded-lg border border-border bg-card p-4">
            <p className="text-sm text-muted-foreground">Prospects</p>
            <p className="text-lg font-semibold">
              +{run.summary?.prospects_created ?? run.prospects_created} / upd{' '}
              {run.summary?.prospects_updated ?? run.prospects_updated}
            </p>
          </div>
        </div>
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
        errorMessage={domainsQ.isError ? getApiErrorMessage(domainsQ.error, 'Failed to load domain results.') : null}
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
