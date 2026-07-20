import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { invalidateAdminCrawler } from '@/features/admin/queryKeys'
import type { AdminBannerHandler } from '@/features/admin/utils'
import { getApiErrorMessage } from '@/shared/api/errors'
import {
  listAdminCrawlerDomains,
  resetAdminFailedCrawlerDomains,
  triggerAdminCrawlerDomain,
} from '@/shared/api/admin'
import type { CrawlDomain } from '@/shared/api/types'
import { DataTable } from '@/shared/components/DataTable'
import { ListPagination } from '@/shared/components/ListPagination'
import { Select } from '@/shared/components/Select'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { useServerList } from '@/shared/hooks/useServerList'

type AdminCrawlerDomainsTableProps = {
  onMessage?: AdminBannerHandler
  initialStatus?: string
  syncUrl?: boolean
}

export function AdminCrawlerDomainsTable({
  onMessage,
  initialStatus = '',
  syncUrl = true,
}: AdminCrawlerDomainsTableProps) {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [domainStatus, setDomainStatus] = useState(
    syncUrl ? (searchParams.get('crawl_status') ?? initialStatus) : initialStatus
  )

  const filters = useMemo(() => (domainStatus ? { crawl_status: domainStatus } : {}), [domainStatus])

  const { items, total, page, pageSize, hasNext, goNext, goPrev, resetPage, query } = useServerList<
    CrawlDomain,
    { crawl_status?: string }
  >({
    queryKey: ['admin', 'crawler', 'domains'],
    queryFn: listAdminCrawlerDomains,
    pageSize: 25,
    filters,
    refetchInterval: (q) => (q.state.data?.items?.some((d) => d.crawl_status === 'crawling') ? 8000 : false),
  })

  useEffect(() => {
    if (!syncUrl) return
    const params = new URLSearchParams()
    if (domainStatus) params.set('crawl_status', domainStatus)
    setSearchParams(params, { replace: true })
    resetPage()
  }, [domainStatus, setSearchParams, resetPage, syncUrl])

  const triggerDomainM = useMutation({
    mutationFn: triggerAdminCrawlerDomain,
    onSuccess: (d) => {
      onMessage?.(`Domain queued. Run #${d.run_id}.`, null)
      invalidateAdminCrawler(qc)
    },
    onError: (err) => onMessage?.(null, getApiErrorMessage(err)),
  })

  const resetFailedM = useMutation({
    mutationFn: () => resetAdminFailedCrawlerDomains(),
    onSuccess: (d) => {
      onMessage?.(`Reset ${d.count} failed domain(s) to pending.`, null)
      invalidateAdminCrawler(qc)
    },
    onError: (err) => onMessage?.(null, getApiErrorMessage(err)),
  })

  const columns = useMemo<ColumnDef<CrawlDomain, unknown>[]>(
    () => [
      {
        accessorKey: 'domain',
        header: 'Domain',
        cell: ({ row }) => <span className="break-all font-mono text-xs">{row.original.domain}</span>,
      },
      {
        accessorKey: 'source_url',
        header: 'Discovery URL',
        cell: ({ row }) =>
          row.original.source_url ? (
            <a
              className="block max-w-xs truncate text-primary underline-offset-2 hover:underline"
              href={row.original.source_url}
              target="_blank"
              rel="noreferrer"
            >
              {row.original.source_url}
            </a>
          ) : (
            '—'
          ),
      },
      {
        accessorKey: 'source_name',
        header: 'Source',
        cell: ({ row }) => row.original.source_name || '—',
      },
      {
        accessorKey: 'crawl_status',
        header: 'Status',
        cell: ({ row }) => <StatusBadge status={row.original.crawl_status} kind="crawl" />,
      },
      { accessorKey: 'crawl_attempts', header: 'Attempts' },
      {
        accessorKey: 'owner_id',
        header: 'Owner',
        cell: ({ row }) => row.original.owner_id ?? '—',
      },
      {
        id: 'actions',
        header: 'Action',
        cell: ({ row }) => (
          <Button
            size="sm"
            variant="outline"
            disabled={triggerDomainM.isPending}
            onClick={() => triggerDomainM.mutate(row.original.id)}
          >
            Crawl now
          </Button>
        ),
      },
    ],
    [triggerDomainM]
  )

  return (
    <div className="space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <Select value={domainStatus} onChange={(e) => setDomainStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="crawling">Crawling</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </Select>
        <div className="flex gap-2">
          <Button variant="outline" size="sm" disabled={resetFailedM.isPending} onClick={() => resetFailedM.mutate()}>
            Reset failed
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
        errorMessage={query.isError ? getApiErrorMessage(query.error, 'Failed to load domains.') : null}
        emptyMessage="No domains match your filters."
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
