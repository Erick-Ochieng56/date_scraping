import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useMemo } from 'react'

import { Button } from '@/components/ui/button'
import { invalidateAdminCrawler } from '@/features/admin/queryKeys'
import type { AdminBannerHandler } from '@/features/admin/utils'
import { getApiErrorMessage } from '@/shared/api/errors'
import { listAdminCrawlerSources, updateAdminCrawlerSource } from '@/shared/api/admin'
import type { CrawlSource } from '@/shared/api/types'
import { DataTable } from '@/shared/components/DataTable'
import { ListPagination } from '@/shared/components/ListPagination'
import { useServerList } from '@/shared/hooks/useServerList'

export function AdminCrawlerSourcesTable({ onMessage }: { onMessage?: AdminBannerHandler }) {
  const qc = useQueryClient()

  const { items, total, page, pageSize, hasNext, goNext, goPrev, query } = useServerList<CrawlSource>({
    queryKey: ['admin', 'crawler', 'sources'],
    queryFn: listAdminCrawlerSources,
    pageSize: 25,
  })

  const sourceM = useMutation({
    mutationFn: ({ sourceId, enabled }: { sourceId: number; enabled: boolean }) =>
      updateAdminCrawlerSource(sourceId, { enabled }),
    onSuccess: () => {
      onMessage?.('Source updated.', null)
      invalidateAdminCrawler(qc)
    },
    onError: (err) => onMessage?.(null, getApiErrorMessage(err)),
  })

  const columns = useMemo<ColumnDef<CrawlSource, unknown>[]>(
    () => [
      { accessorKey: 'name', header: 'Source' },
      { accessorKey: 'source_type', header: 'Type' },
      { accessorKey: 'priority', header: 'Priority' },
      {
        accessorKey: 'enabled',
        header: 'Enabled',
        cell: ({ row }) => (row.original.enabled ? 'Yes' : 'No'),
      },
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
            disabled={sourceM.isPending}
            onClick={() => sourceM.mutate({ sourceId: row.original.id, enabled: !row.original.enabled })}
          >
            {row.original.enabled ? 'Disable' : 'Enable'}
          </Button>
        ),
      },
    ],
    [sourceM]
  )

  return (
    <div className="space-y-3">
      <div className="flex justify-end">
        <Button variant="outline" size="sm" onClick={() => void query.refetch()}>
          Refresh
        </Button>
      </div>
      <DataTable
        columns={columns}
        data={items}
        isLoading={query.isLoading}
        errorMessage={query.isError ? getApiErrorMessage(query.error, 'Failed to load crawl sources.') : null}
        emptyMessage="No crawl sources found."
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
