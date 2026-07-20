import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useMemo } from 'react'

import { Button } from '@/components/ui/button'
import { invalidateAdminScraper } from '@/features/admin/queryKeys'
import type { AdminBannerHandler } from '@/features/admin/utils'
import { getApiErrorMessage } from '@/shared/api/errors'
import { listAdminScraperTargets, triggerAdminScraperTarget } from '@/shared/api/admin'
import type { AdminScraperTarget } from '@/shared/api/types'
import { DataTable } from '@/shared/components/DataTable'
import { ListPagination } from '@/shared/components/ListPagination'
import { useServerList } from '@/shared/hooks/useServerList'

export function AdminScraperTargetsTable({ onMessage }: { onMessage?: AdminBannerHandler }) {
  const qc = useQueryClient()

  const { items, total, page, pageSize, hasNext, goNext, goPrev, query } = useServerList<AdminScraperTarget>({
    queryKey: ['admin', 'scraper', 'targets'],
    queryFn: listAdminScraperTargets,
    pageSize: 25,
  })

  const triggerM = useMutation({
    mutationFn: triggerAdminScraperTarget,
    onSuccess: (d) => {
      onMessage?.(d.message ?? 'Scrape triggered.', null)
      invalidateAdminScraper(qc)
    },
    onError: (err) => onMessage?.(null, getApiErrorMessage(err)),
  })

  const columns = useMemo<ColumnDef<AdminScraperTarget, unknown>[]>(
    () => [
      { accessorKey: 'name', header: 'Target' },
      { accessorKey: 'target_type', header: 'Type' },
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
            disabled={triggerM.isPending}
            onClick={() => triggerM.mutate(row.original.id)}
          >
            Trigger scrape
          </Button>
        ),
      },
    ],
    [triggerM]
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
        errorMessage={query.isError ? getApiErrorMessage(query.error, 'Failed to load scrape targets.') : null}
        emptyMessage="No scrape targets found."
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
