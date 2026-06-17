import { useQuery } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { adminKeys } from '@/features/admin/queryKeys'
import { fmtDate } from '@/features/admin/utils'
import { listAdminActivity } from '@/shared/api/admin'
import type { ActivityLogEntry } from '@/shared/api/types'
import { DataTable } from '@/shared/components/DataTable'
import { Input } from '@/shared/components/Input'
import { ListPagination } from '@/shared/components/ListPagination'
import { PageHeader } from '@/shared/components/PageHeader'
import { Select } from '@/shared/components/Select'
import { useDebouncedValue } from '@/shared/hooks/useDebouncedValue'

export function AdminAuditPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [page, setPage] = useState(Number(searchParams.get('page') || 1) || 1)
  const [action, setAction] = useState(searchParams.get('action') ?? '')
  const [objectType, setObjectType] = useState(searchParams.get('object_type') ?? '')
  const [search, setSearch] = useState(searchParams.get('search') ?? '')
  const debouncedSearch = useDebouncedValue(search, 300)
  const pageSize = 30

  const activityQ = useQuery({
    queryKey: adminKeys.activity({ page, action, objectType, search: debouncedSearch }),
    queryFn: () =>
      listAdminActivity({
        page,
        page_size: pageSize,
        action: action || undefined,
        object_type: objectType || undefined,
        search: debouncedSearch.trim() || undefined,
      }),
  })

  useEffect(() => {
    const params = new URLSearchParams()
    if (page > 1) params.set('page', String(page))
    if (action) params.set('action', action)
    if (objectType) params.set('object_type', objectType)
    if (search.trim()) params.set('search', search.trim())
    setSearchParams(params, { replace: true })
  }, [page, action, objectType, search, setSearchParams])

  const rows = activityQ.data?.items.items ?? []
  const total = activityQ.data?.items.total ?? 0
  const hasNext = activityQ.data?.items.has_next ?? false
  const actionChoices = activityQ.data?.filters.actions ?? []

  const columns = useMemo<ColumnDef<ActivityLogEntry, unknown>[]>(
    () => [
      {
        accessorKey: 'created_at',
        header: 'When',
        cell: ({ row }) => <span className="whitespace-nowrap">{fmtDate(row.original.created_at)}</span>,
      },
      {
        accessorKey: 'username',
        header: 'Actor',
        cell: ({ row }) => row.original.username ?? '—',
      },
      { accessorKey: 'action_display', header: 'Action' },
      {
        id: 'object',
        header: 'Object',
        cell: ({ row }) => (
          <span>
            {row.original.object_type} #{row.original.object_id}
          </span>
        ),
      },
      {
        accessorKey: 'description',
        header: 'Description',
        cell: ({ row }) => <span className="max-w-xl">{row.original.description}</span>,
      },
    ],
    []
  )

  const applyFilters = () => setPage(1)

  return (
    <div className="space-y-4">
      <PageHeader
        title="Audit log"
        description="Immutable admin and staff action timeline. Filter by action, object type, or description text."
        actions={
          <Button variant="outline" asChild>
            <Link to="/admin">Back to admin home</Link>
          </Button>
        }
      />

      <div className="flex flex-wrap items-end gap-3 rounded-lg border border-border bg-card p-4">
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Action</span>
          <Select value={action} onChange={(e) => setAction(e.target.value)}>
            <option value="">All actions</option>
            {actionChoices.map((c) => (
              <option key={c.value} value={c.value}>
                {c.label}
              </option>
            ))}
          </Select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Object type</span>
          <Input
            className="w-40"
            placeholder="e.g. user"
            value={objectType}
            onChange={(e) => setObjectType(e.target.value)}
          />
        </label>
        <label className="flex min-w-[12rem] flex-1 flex-col gap-1 text-sm">
          <span className="text-muted-foreground">Search description</span>
          <Input
            placeholder="Keyword in description"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter') applyFilters()
            }}
          />
        </label>
        <Button variant="outline" size="sm" onClick={applyFilters}>
          Apply filters
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={rows}
        isLoading={activityQ.isLoading}
        emptyMessage="No audit entries match these filters."
        getRowId={(r) => String(r.id)}
      />

      <ListPagination
        page={page}
        pageSize={pageSize}
        total={total}
        hasNext={hasNext}
        onPrev={() => setPage((p) => Math.max(1, p - 1))}
        onNext={() => setPage((p) => p + 1)}
        isLoading={activityQ.isFetching}
      />
    </div>
  )
}
