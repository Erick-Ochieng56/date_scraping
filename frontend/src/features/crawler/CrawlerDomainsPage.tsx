import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useEffect, useMemo, useState } from 'react'
import { useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { invalidateCrawlerQueries } from '@/features/crawler/queryKeys'
import { getApiErrorMessage } from '@/shared/api/errors'
import { listCrawlDomains, triggerCrawlDomain } from '@/shared/api/crawler'
import type { CrawlDomain } from '@/shared/api/types'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { DataTable } from '@/shared/components/DataTable'
import { Input } from '@/shared/components/Input'
import { ListPagination } from '@/shared/components/ListPagination'
import { PageHeader } from '@/shared/components/PageHeader'
import { Select } from '@/shared/components/Select'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { useServerList } from '@/shared/hooks/useServerList'

export function CrawlerDomainsPage() {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState(searchParams.get('search') ?? '')
  const [crawlStatus, setCrawlStatus] = useState(searchParams.get('crawl_status') ?? '')
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  const { items, total, page, pageSize, hasNext, goNext, goPrev, resetPage, query } = useServerList<
    CrawlDomain,
    { crawl_status?: string }
  >({
    queryKey: ['crawler', 'domains'],
    queryFn: listCrawlDomains,
    pageSize: 25,
    filters: crawlStatus ? { crawl_status: crawlStatus } : {},
    search,
    refetchInterval: (q) => (q.state.data?.items?.some((d) => d.crawl_status === 'crawling') ? 8000 : false),
  })

  useEffect(() => {
    const params = new URLSearchParams()
    if (crawlStatus) params.set('crawl_status', crawlStatus)
    if (search.trim()) params.set('search', search.trim())
    setSearchParams(params, { replace: true })
    resetPage()
  }, [crawlStatus, search, setSearchParams, resetPage])

  const triggerM = useMutation({
    mutationFn: (domainId: number) => triggerCrawlDomain(domainId),
    onSuccess: (data) => {
      setBanner({ message: `Crawl started (run #${data.run_id}).` })
      invalidateCrawlerQueries(qc)
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
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
        id: 'actions',
        header: 'Action',
        cell: ({ row }) => (
          <Button
            size="sm"
            disabled={triggerM.isPending}
            onClick={() => {
              const ok = window.confirm(`Start a manual crawl for ${row.original.domain}?`)
              if (ok) triggerM.mutate(row.original.id)
            }}
          >
            Crawl now
          </Button>
        ),
      },
    ],
    [triggerM]
  )

  return (
    <div className="space-y-4">
      <PageHeader
        title="Websites found"
        description="Sites found by search or scheduled discovery, waiting to be crawled."
      />

      <AlertBanner message={banner.message} error={banner.error} />

      <div className="flex flex-wrap gap-2">
        <Input
          className="min-w-[240px] flex-1"
          placeholder="Search domain…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select value={crawlStatus} onChange={(e) => setCrawlStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="crawling">Crawling</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </Select>
        <Button variant="outline" onClick={() => void query.refetch()}>
          Refresh
        </Button>
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
