import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { adminKeys, invalidateAdminCrawler } from '@/features/admin/queryKeys'
import { crawlTriggerLabel } from '@/features/crawler/utils'
import type { AdminBannerHandler } from '@/features/admin/utils'
import { getApiErrorMessage } from '@/shared/api/errors'
import { cancelAdminCrawlerRun, cancelAllAdminCrawlerRuns, listAdminCrawlerRuns } from '@/shared/api/admin'
import type { CrawlRun } from '@/shared/api/types'
import { DataTable } from '@/shared/components/DataTable'
import { ListPagination } from '@/shared/components/ListPagination'
import { RunStatusBadge } from '@/shared/components/RunStatusBadge'
import { Select } from '@/shared/components/Select'
import { pollIntervalWhenRunning } from '@/shared/hooks/usePollWhen'
import { useServerList } from '@/shared/hooks/useServerList'

type AdminCrawlerRunsTableProps = {
  onMessage?: AdminBannerHandler
  initialStatus?: string
  syncUrl?: boolean
}

export function AdminCrawlerRunsTable({ onMessage, initialStatus = '', syncUrl = true }: AdminCrawlerRunsTableProps) {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [runStatus, setRunStatus] = useState(syncUrl ? (searchParams.get('status') ?? initialStatus) : initialStatus)

  const filters = useMemo(() => (runStatus ? { status: runStatus } : {}), [runStatus])

  const { items, total, page, pageSize, hasNext, goNext, goPrev, resetPage, query } = useServerList<
    CrawlRun,
    { status?: string }
  >({
    queryKey: ['admin', 'crawler', 'runs'],
    queryFn: listAdminCrawlerRuns,
    pageSize: 25,
    filters,
    refetchInterval: (q) => pollIntervalWhenRunning(undefined, q.state.data?.items, 8000),
  })

  const failedCountQ = useQuery({
    queryKey: adminKeys.crawler.failedCount,
    queryFn: () => listAdminCrawlerRuns({ page_size: 1, status: 'failed' }),
  })

  useEffect(() => {
    if (!syncUrl) return
    const params = new URLSearchParams()
    if (runStatus) params.set('status', runStatus)
    setSearchParams(params, { replace: true })
    resetPage()
  }, [runStatus, setSearchParams, resetPage, syncUrl])

  const cancelRunM = useMutation({
    mutationFn: cancelAdminCrawlerRun,
    onSuccess: (d) => {
      onMessage?.(d.message ?? 'Run cancelled.', null)
      invalidateAdminCrawler(qc)
    },
    onError: (err) => onMessage?.(null, getApiErrorMessage(err)),
  })

  const cancelAllM = useMutation({
    mutationFn: cancelAllAdminCrawlerRuns,
    onSuccess: (d) => {
      onMessage?.(`Cancelled ${d.cancelled} running run(s).`, null)
      invalidateAdminCrawler(qc)
    },
    onError: (err) => onMessage?.(null, getApiErrorMessage(err)),
  })

  const columns = useMemo<ColumnDef<CrawlRun, unknown>[]>(
    () => [
      {
        accessorKey: 'id',
        header: 'Run',
        cell: ({ row }) => <span className="font-medium">#{row.original.id}</span>,
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
      {
        accessorKey: 'owner_id',
        header: 'Owner',
        cell: ({ row }) => row.original.owner_id ?? '—',
      },
      {
        accessorKey: 'started_at',
        header: 'Started',
        cell: ({ row }) => (row.original.started_at ? new Date(row.original.started_at).toLocaleString() : '—'),
      },
      ...(runStatus === 'failed'
        ? [
            {
              accessorKey: 'error_text',
              header: 'Error',
              cell: ({ row }: { row: { original: CrawlRun } }) => (
                <span className="max-w-xs truncate text-xs text-muted-foreground" title={row.original.error_text}>
                  {row.original.error_text || '—'}
                </span>
              ),
            } as ColumnDef<CrawlRun, unknown>,
          ]
        : []),
      {
        id: 'actions',
        header: 'Action',
        cell: ({ row }) =>
          row.original.status === 'running' ? (
            <Button
              size="sm"
              variant="outline"
              disabled={cancelRunM.isPending}
              onClick={() => cancelRunM.mutate(row.original.id)}
            >
              Cancel run
            </Button>
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          ),
      },
    ],
    [cancelRunM, runStatus]
  )

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Select value={runStatus} onChange={(e) => setRunStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="running">Running</option>
          <option value="success">Success</option>
          <option value="failed">Failed</option>
        </Select>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={cancelAllM.isPending} onClick={() => cancelAllM.mutate()}>
            Cancel all running
          </Button>
          <Button variant="outline" size="sm" onClick={() => void query.refetch()}>
            Refresh
          </Button>
        </div>
      </div>
      <DataTable
        columns={columns}
        data={items}
        isLoading={query.isLoading}
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
      <p className="text-xs text-muted-foreground">Failed runs (total): {failedCountQ.data?.total ?? 0}</p>
    </div>
  )
}
