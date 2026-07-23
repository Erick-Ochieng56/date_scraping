import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { getApiErrorMessage } from '@/shared/api/errors'
import { listScrapeRuns, listTargets, retryScrapeRun, triggerTarget } from '@/shared/api/scraper'
import type { ScrapeRun } from '@/shared/api/types'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { DataTable } from '@/shared/components/DataTable'
import { ListPagination } from '@/shared/components/ListPagination'
import { PageHeader } from '@/shared/components/PageHeader'
import { RunStatusBadge } from '@/shared/components/RunStatusBadge'
import { Select } from '@/shared/components/Select'
import { pollIntervalWhenRunning } from '@/shared/hooks/usePollWhen'
import { useServerList } from '@/shared/hooks/useServerList'
import { summarizeScrapeRun } from '@/shared/utils/runSummary'

export function RunsPage() {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const initialTarget = Number(searchParams.get('target_id') || '') || 0
  const [targetId, setTargetId] = useState(initialTarget)
  const [statusFilter, setStatusFilter] = useState(searchParams.get('status') ?? '')
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  const filters = useMemo(
    () => ({
      ...(targetId ? { target_id: targetId } : {}),
      ...(statusFilter ? { status: statusFilter } : {}),
    }),
    [targetId, statusFilter]
  )

  const { items, total, page, pageSize, hasNext, goNext, goPrev, resetPage, query } = useServerList<
    ScrapeRun,
    { target_id?: number; status?: string }
  >({
    queryKey: ['scrape-runs'],
    queryFn: listScrapeRuns,
    pageSize: 25,
    filters,
    refetchInterval: (q) => pollIntervalWhenRunning(undefined, q.state.data?.items, 5000),
  })

  useEffect(() => {
    const params = new URLSearchParams()
    if (targetId) params.set('target_id', String(targetId))
    if (statusFilter) params.set('status', statusFilter)
    setSearchParams(params, { replace: true })
    resetPage()
  }, [targetId, statusFilter, setSearchParams, resetPage])

  const targetsQ = useQuery({
    queryKey: ['targets-run-filter'],
    queryFn: () => listTargets({ page_size: 200 }),
  })

  const retryM = useMutation({
    mutationFn: (runId: number) => retryScrapeRun(runId),
    onSuccess: () => {
      setBanner({ message: 'Retry queued.' })
      void qc.invalidateQueries({ queryKey: ['scrape-runs'] })
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const triggerTargetM = useMutation({
    mutationFn: (selectedTargetId: number) => triggerTarget(selectedTargetId),
    onSuccess: (data) => {
      setBanner({ message: data.message ?? 'Scrape queued.' })
      void qc.invalidateQueries({ queryKey: ['scrape-runs'] })
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const columns = useMemo<ColumnDef<ScrapeRun, unknown>[]>(
    () => [
      {
        accessorKey: 'id',
        header: 'Check',
        cell: ({ row }) => (
          <Link className="font-medium text-primary hover:underline" to={`/runs/${row.original.id}`}>
            #{row.original.id}
          </Link>
        ),
      },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => (
          <RunStatusBadge status={row.original.status} display={row.original.status_display || row.original.status} />
        ),
      },
      {
        id: 'summary',
        header: 'Summary',
        cell: ({ row }) => <span className="text-sm">{summarizeScrapeRun(row.original)}</span>,
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
        id: 'actions',
        header: 'Actions',
        cell: ({ row }) =>
          row.original.status === 'failed' ? (
            <Button size="sm" disabled={retryM.isPending} onClick={() => retryM.mutate(row.original.id)}>
              Retry
            </Button>
          ) : (
            <span className="text-muted-foreground">—</span>
          ),
      },
    ],
    [retryM]
  )

  return (
    <div className="space-y-4">
      <PageHeader
        title="Check history"
        description="Past site checks, most recent first. This list updates automatically while a check is running."
        actions={
          <>
            <Button
              disabled={!targetId || triggerTargetM.isPending}
              onClick={() => targetId && triggerTargetM.mutate(targetId)}
            >
              {triggerTargetM.isPending ? 'Starting…' : 'Check selected site'}
            </Button>
            <Button variant="outline" onClick={() => void query.refetch()}>
              Refresh
            </Button>
          </>
        }
      />

      <AlertBanner message={banner.message} error={banner.error} />

      <div className="flex flex-wrap gap-2">
        <Select
          value={targetId}
          onChange={(e) => setTargetId(Number(e.target.value))}
          className="min-w-[12rem]"
        >
          <option value={0}>All sites</option>
          {(targetsQ.data?.items ?? []).map((t) => (
            <option key={t.id} value={t.id}>
              {t.name}
            </option>
          ))}
        </Select>
        <Select value={statusFilter} onChange={(e) => setStatusFilter(e.target.value)}>
          <option value="">All statuses</option>
          <option value="running">Running</option>
          <option value="success">Success</option>
          <option value="failed">Failed</option>
        </Select>
      </div>

      <DataTable
        columns={columns}
        data={items}
        isLoading={query.isLoading}
        errorMessage={query.isError ? getApiErrorMessage(query.error, 'Failed to load check history.') : null}
        emptyMessage="No checks match your filters."
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
