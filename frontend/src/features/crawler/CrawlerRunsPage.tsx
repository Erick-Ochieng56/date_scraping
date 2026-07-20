import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { invalidateCrawlerQueries } from '@/features/crawler/queryKeys'
import { crawlTriggerLabel, truncateText } from '@/features/crawler/utils'
import { getApiErrorMessage } from '@/shared/api/errors'
import { cancelAllRunningCrawls, cancelCrawlRun, listCrawlRuns, triggerCrawler } from '@/shared/api/crawler'
import type { CrawlRun } from '@/shared/api/types'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { DataTable } from '@/shared/components/DataTable'
import { ListPagination } from '@/shared/components/ListPagination'
import { PageHeader } from '@/shared/components/PageHeader'
import { RunStatusBadge } from '@/shared/components/RunStatusBadge'
import { Select } from '@/shared/components/Select'
import { pollIntervalWhenRunning } from '@/shared/hooks/usePollWhen'
import { useServerList } from '@/shared/hooks/useServerList'

export function CrawlerRunsPage() {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') ?? '')
  const [triggerFilter, setTriggerFilter] = useState(searchParams.get('trigger') ?? '')
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  const filters = useMemo(
    () => ({
      ...(statusFilter ? { status: statusFilter } : {}),
      ...(triggerFilter ? { trigger: triggerFilter } : {}),
    }),
    [statusFilter, triggerFilter]
  )

  const { items, total, page, pageSize, hasNext, goNext, goPrev, resetPage, query } = useServerList<
    CrawlRun,
    { status?: string; trigger?: string }
  >({
    queryKey: ['crawler', 'runs'],
    queryFn: listCrawlRuns,
    pageSize: 25,
    filters,
    refetchInterval: (q) => {
      const polling = pollIntervalWhenRunning(undefined, q.state.data?.items, 5000)
      if (polling) return polling
      if (!statusFilter) return 15000
      return false
    },
  })

  useEffect(() => {
    const params = new URLSearchParams()
    if (statusFilter) params.set('status', statusFilter)
    if (triggerFilter) params.set('trigger', triggerFilter)
    setSearchParams(params, { replace: true })
    resetPage()
  }, [statusFilter, triggerFilter, setSearchParams, resetPage])

  const triggerM = useMutation({
    mutationFn: triggerCrawler,
    onSuccess: (data) => {
      setBanner({ message: data.message ?? 'Discovery queued.' })
      invalidateCrawlerQueries(qc)
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const cancelAllM = useMutation({
    mutationFn: cancelAllRunningCrawls,
    onSuccess: (data) => {
      setBanner({ message: `Cancelled ${data.cancelled ?? 0} run(s).` })
      invalidateCrawlerQueries(qc)
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const cancelOneM = useMutation({
    mutationFn: (runId: number) => cancelCrawlRun(runId),
    onSuccess: () => {
      setBanner({ message: 'Run cancelled.' })
      invalidateCrawlerQueries(qc)
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const columns = useMemo<ColumnDef<CrawlRun, unknown>[]>(
    () => [
      {
        accessorKey: 'id',
        header: 'Run',
        cell: ({ row }) => (
          <Link className="font-medium text-primary hover:underline" to={`/crawler/runs/${row.original.id}`}>
            #{row.original.id}
          </Link>
        ),
      },
      {
        accessorKey: 'trigger',
        header: 'Trigger',
        cell: ({ row }) => crawlTriggerLabel(row.original.trigger),
      },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => (
          <RunStatusBadge status={row.original.status} display={row.original.status_display || row.original.status} />
        ),
      },
      { accessorKey: 'domains_queued', header: 'Domains' },
      {
        id: 'prospects',
        header: 'Prospects',
        cell: ({ row }) => (
          <span>
            +{row.original.prospects_created} / upd {row.original.prospects_updated}
          </span>
        ),
      },
      {
        accessorKey: 'started_at',
        header: 'Started',
        cell: ({ row }) => new Date(row.original.started_at).toLocaleString(),
      },
      {
        accessorKey: 'finished_at',
        header: 'Finished',
        cell: ({ row }) =>
          row.original.finished_at ? new Date(row.original.finished_at).toLocaleString() : '—',
      },
      {
        accessorKey: 'error_text',
        header: 'Last error',
        cell: ({ row }) => (
          <span className="max-w-[220px] text-muted-foreground" title={row.original.error_text || undefined}>
            {row.original.error_text ? truncateText(row.original.error_text) : '—'}
          </span>
        ),
      },
      {
        id: 'actions',
        header: 'Actions',
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-2">
            <Button size="sm" variant="outline" asChild>
              <Link to={`/crawler/runs/${row.original.id}`}>Details</Link>
            </Button>
            {row.original.status === 'running' ? (
              <Button
                size="sm"
                variant="outline"
                disabled={cancelOneM.isPending}
                onClick={() => {
                  const ok = window.confirm(`Cancel crawl run #${row.original.id}?`)
                  if (ok) cancelOneM.mutate(row.original.id)
                }}
              >
                Cancel
              </Button>
            ) : null}
          </div>
        ),
      },
    ],
    [cancelOneM]
  )

  return (
    <div className="space-y-4">
      <PageHeader
        title="Crawl runs"
        description="Discovery and domain crawl jobs — separate from manual scraper runs under Scraper."
        actions={
          <>
            <Button variant="outline" onClick={() => void query.refetch()}>
              Refresh
            </Button>
            <Button
              variant="outline"
              disabled={cancelAllM.isPending}
              onClick={() => {
                const ok = window.confirm('Cancel all currently running crawl runs?')
                if (ok) cancelAllM.mutate()
              }}
            >
              {cancelAllM.isPending ? 'Cancelling…' : 'Cancel all running'}
            </Button>
            <Button disabled={triggerM.isPending} onClick={() => triggerM.mutate()}>
              {triggerM.isPending ? 'Queueing…' : 'Trigger crawler'}
            </Button>
          </>
        }
      />

      <AlertBanner message={banner.message} error={banner.error} />

      <div className="flex flex-wrap gap-2">
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="running">Running</option>
          <option value="success">Success</option>
          <option value="failed">Failed</option>
        </Select>
        <Select value={triggerFilter} onChange={(e) => setTriggerFilter(e.target.value)}>
          <option value="">All triggers</option>
          <option value="manual">Manual</option>
          <option value="scheduled">Scheduled</option>
        </Select>
      </div>

      <DataTable
        columns={columns}
        data={items}
        isLoading={query.isLoading}
        errorMessage={query.isError ? getApiErrorMessage(query.error, 'Failed to load crawl runs.') : null}
        emptyMessage="No crawl runs match your filters."
        getRowId={(r) => String(r.id)}
      />

      <ListPagination
        page={page}
        pageSize={pageSize}
        total={total}
        hasNext={hasNext}
        onPrev={goPrev}
        onNext={goNext}
        isLoading={query.isFetching}
      />
    </div>
  )
}
