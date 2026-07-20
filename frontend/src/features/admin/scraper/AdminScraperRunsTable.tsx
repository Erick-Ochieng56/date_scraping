import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { invalidateAdminScraper } from '@/features/admin/queryKeys'
import type { AdminBannerHandler } from '@/features/admin/utils'
import { getApiErrorMessage } from '@/shared/api/errors'
import { listAdminScrapeRuns, retryAdminScrapeRun } from '@/shared/api/admin'
import type { AdminScrapeRun } from '@/shared/api/types'
import { DataTable } from '@/shared/components/DataTable'
import { ListPagination } from '@/shared/components/ListPagination'
import { RunStatusBadge } from '@/shared/components/RunStatusBadge'
import { Select } from '@/shared/components/Select'
import { pollIntervalWhenRunning } from '@/shared/hooks/usePollWhen'
import { useServerList } from '@/shared/hooks/useServerList'

type AdminScraperRunsTableProps = {
  onMessage?: AdminBannerHandler
  initialStatus?: string
  syncUrl?: boolean
}

export function AdminScraperRunsTable({ onMessage, initialStatus = '', syncUrl = true }: AdminScraperRunsTableProps) {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [statusFilter, setStatusFilter] = useState(
    syncUrl ? (searchParams.get('status') ?? initialStatus) : initialStatus
  )

  const filters = useMemo(() => (statusFilter ? { status: statusFilter } : {}), [statusFilter])

  const { items, total, page, pageSize, hasNext, goNext, goPrev, resetPage, query } = useServerList<
    AdminScrapeRun,
    { status?: string }
  >({
    queryKey: ['admin', 'scraper', 'runs'],
    queryFn: listAdminScrapeRuns,
    pageSize: 25,
    filters,
    refetchInterval: (q) => pollIntervalWhenRunning(undefined, q.state.data?.items, 8000),
  })

  useEffect(() => {
    if (!syncUrl) return
    const params = new URLSearchParams()
    if (statusFilter) params.set('status', statusFilter)
    setSearchParams(params, { replace: true })
    resetPage()
  }, [statusFilter, setSearchParams, resetPage, syncUrl])

  const retryM = useMutation({
    mutationFn: retryAdminScrapeRun,
    onSuccess: (d) => {
      onMessage?.(d.message ?? 'Retry queued.', null)
      invalidateAdminScraper(qc)
    },
    onError: (err) => onMessage?.(null, getApiErrorMessage(err)),
  })

  const columns = useMemo<ColumnDef<AdminScrapeRun, unknown>[]>(
    () => [
      {
        accessorKey: 'id',
        header: 'Run',
        cell: ({ row }) => <span className="font-medium">#{row.original.id}</span>,
      },
      { accessorKey: 'target_name', header: 'Target' },
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
      ...(statusFilter === 'failed'
        ? [
            {
              accessorKey: 'error_text',
              header: 'Error',
              cell: ({ row }: { row: { original: AdminScrapeRun } }) => (
                <span className="max-w-xs truncate text-xs text-muted-foreground" title={row.original.error_text}>
                  {row.original.error_text || '—'}
                </span>
              ),
            } as ColumnDef<AdminScrapeRun, unknown>,
          ]
        : []),
      {
        id: 'actions',
        header: 'Action',
        cell: ({ row }) =>
          row.original.status === 'failed' ? (
            <Button
              size="sm"
              variant="outline"
              disabled={retryM.isPending}
              onClick={() => retryM.mutate(row.original.id)}
            >
              Retry
            </Button>
          ) : (
            <span className="text-xs text-muted-foreground">—</span>
          ),
      },
    ],
    [retryM, statusFilter]
  )

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="running">Running</option>
          <option value="success">Success</option>
          <option value="failed">Failed</option>
        </Select>
        <Button variant="outline" size="sm" onClick={() => void query.refetch()}>
          Refresh
        </Button>
      </div>
      <DataTable
        columns={columns}
        data={items}
        isLoading={query.isLoading}
        errorMessage={query.isError ? getApiErrorMessage(query.error, 'Failed to load scrape runs.') : null}
        emptyMessage="No scrape runs match your filters."
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
