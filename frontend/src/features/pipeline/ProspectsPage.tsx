import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { DataTable } from '@/shared/components/DataTable'
import { Input } from '@/shared/components/Input'
import { ListPagination } from '@/shared/components/ListPagination'
import { PageHeader } from '@/shared/components/PageHeader'
import { Select } from '@/shared/components/Select'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { getApiErrorMessage } from '@/shared/api/errors'
import {
  listProspects,
  prospectConvert,
  prospectMarkContacted,
  prospectReject,
  prospectsBulkContacted,
  prospectsBulkConvert,
  prospectsBulkReject,
  prospectsExportUrl,
} from '@/shared/api/pipeline'
import type { Prospect } from '@/shared/api/types'
import { useRowSelection } from '@/shared/hooks/useRowSelection'
import { useServerList } from '@/shared/hooks/useServerList'

function fmtEventDate(v: string | null) {
  if (!v) return '—'
  return new Date(v).toLocaleDateString()
}

export function ProspectsPage() {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState(searchParams.get('search') ?? '')
  const [status, setStatus] = useState(searchParams.get('status') ?? '')
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  const selection = useRowSelection<Prospect['id']>((r) => r.id)

  const { items, total, page, pageSize, hasNext, goNext, goPrev, resetPage, query } = useServerList<
    Prospect,
    { status?: string }
  >({
    queryKey: ['prospects'],
    queryFn: listProspects,
    pageSize: 25,
    filters: status ? { status } : {},
    search,
  })

  useEffect(() => {
    const params = new URLSearchParams()
    if (status) params.set('status', status)
    if (search.trim()) params.set('search', search.trim())
    setSearchParams(params, { replace: true })
    resetPage()
  }, [status, search, setSearchParams, resetPage])

  const refresh = () => {
    selection.clear()
    setBanner({})
    void qc.invalidateQueries({ queryKey: ['prospects'] })
    void qc.invalidateQueries({ queryKey: ['leads'] })
  }

  const onMutationError = (err: unknown) => setBanner({ error: getApiErrorMessage(err) })

  const contactM = useMutation({
    mutationFn: () => prospectsBulkContacted(selection.selected),
    onSuccess: () => {
      setBanner({ message: 'Marked selected prospects as contacted.' })
      refresh()
    },
    onError: onMutationError,
  })
  const convertM = useMutation({
    mutationFn: () => prospectsBulkConvert(selection.selected),
    onSuccess: () => {
      setBanner({ message: 'Converted selected prospects to leads.' })
      refresh()
    },
    onError: onMutationError,
  })
  const rejectM = useMutation({
    mutationFn: () => prospectsBulkReject(selection.selected),
    onSuccess: () => {
      setBanner({ message: 'Rejected selected prospects.' })
      refresh()
    },
    onError: onMutationError,
  })
  const rowContactM = useMutation({
    mutationFn: (id: number) => prospectMarkContacted(id),
    onSuccess: refresh,
    onError: onMutationError,
  })
  const rowConvertM = useMutation({
    mutationFn: (id: number) => prospectConvert(id),
    onSuccess: refresh,
    onError: onMutationError,
  })
  const rowRejectM = useMutation({
    mutationFn: (id: number) => prospectReject(id),
    onSuccess: refresh,
    onError: onMutationError,
  })

  const columns = useMemo<ColumnDef<Prospect, unknown>[]>(
    () => [
      {
        id: 'select',
        header: () => (
          <input
            type="checkbox"
            aria-label="Select all on page"
            checked={selection.isAllSelected(items)}
            onChange={(e) => selection.toggleAll(items, e.target.checked)}
          />
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            aria-label={`Select prospect ${row.original.id}`}
            checked={selection.selected.includes(row.original.id)}
            onChange={(e) => selection.toggle(row.original.id, e.target.checked)}
          />
        ),
      },
      {
        accessorKey: 'company',
        header: 'Company',
        cell: ({ row }) => row.original.company || '—',
      },
      {
        accessorKey: 'event_name',
        header: 'Event',
        cell: ({ row }) => row.original.event_name || '—',
      },
      {
        accessorKey: 'event_date',
        header: 'Event date',
        cell: ({ row }) => fmtEventDate(row.original.event_date),
      },
      {
        accessorKey: 'email',
        header: 'Email',
        cell: ({ row }) => row.original.email || '—',
      },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => <StatusBadge status={row.original.status} kind="prospect" />,
      },
      {
        id: 'actions',
        header: 'Actions',
        cell: ({ row }) => {
          const p = row.original
          return (
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" asChild>
                <Link to={`/prospects/${p.id}`}>View</Link>
              </Button>
              <Button
                size="sm"
                disabled={p.status !== 'new' || rowContactM.isPending}
                onClick={() => rowContactM.mutate(p.id)}
              >
                Contacted
              </Button>
              <Button
                size="sm"
                disabled={!['new', 'contacted'].includes(p.status) || rowConvertM.isPending}
                onClick={() => rowConvertM.mutate(p.id)}
              >
                Convert
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={p.status === 'rejected' || rowRejectM.isPending}
                onClick={() => rowRejectM.mutate(p.id)}
              >
                Reject
              </Button>
            </div>
          )
        },
      },
    ],
    [items, selection, rowContactM, rowConvertM, rowRejectM]
  )

  return (
    <div className="space-y-4">
      <PageHeader
        title="Prospects"
        description="Review crawler discoveries and move qualified contacts into the lead pipeline."
        actions={
          <>
            <Button variant="outline" asChild>
              <a href={prospectsExportUrl()}>Export CSV</a>
            </Button>
            <Button disabled={!selection.canBulk || contactM.isPending} onClick={() => contactM.mutate()}>
              Mark contacted
            </Button>
            <Button disabled={!selection.canBulk || convertM.isPending} onClick={() => convertM.mutate()}>
              Convert to leads
            </Button>
            <Button variant="outline" disabled={!selection.canBulk || rejectM.isPending} onClick={() => rejectM.mutate()}>
              Reject
            </Button>
          </>
        }
      />

      <AlertBanner message={banner.message} error={banner.error} />

      <div className="flex flex-wrap gap-2">
        <Input
          className="min-w-[240px] flex-1"
          placeholder="Search company, event, email…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="new">New</option>
          <option value="contacted">Contacted</option>
          <option value="converted">Converted</option>
          <option value="rejected">Rejected</option>
        </Select>
        <Button variant="outline" onClick={() => void query.refetch()}>
          Refresh
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={items}
        isLoading={query.isLoading}
        errorMessage={query.isError ? getApiErrorMessage(query.error, 'Failed to load prospects.') : null}
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
