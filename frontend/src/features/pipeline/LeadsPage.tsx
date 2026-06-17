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
  leadMarkInterested,
  leadReject,
  leadSyncCrm,
  leadsBulkInterested,
  leadsBulkReject,
  leadsExportUrl,
  listLeads,
} from '@/shared/api/pipeline'
import type { Lead } from '@/shared/api/types'
import { useRowSelection } from '@/shared/hooks/useRowSelection'
import { useServerList } from '@/shared/hooks/useServerList'

export function LeadsPage() {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState(searchParams.get('search') ?? '')
  const [status, setStatus] = useState(searchParams.get('status') ?? '')
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  const selection = useRowSelection<Lead['id']>((r) => r.id)

  const { items, total, page, pageSize, hasNext, goNext, goPrev, resetPage, query } = useServerList<Lead, { status?: string }>({
    queryKey: ['leads'],
    queryFn: listLeads,
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
    void qc.invalidateQueries({ queryKey: ['leads'] })
  }

  const onMutationError = (err: unknown) => setBanner({ error: getApiErrorMessage(err) })

  const interestedM = useMutation({
    mutationFn: () => leadsBulkInterested(selection.selected),
    onSuccess: () => {
      setBanner({ message: 'Marked selected leads as interested.' })
      refresh()
    },
    onError: onMutationError,
  })
  const rejectM = useMutation({
    mutationFn: () => leadsBulkReject(selection.selected),
    onSuccess: () => {
      setBanner({ message: 'Rejected selected leads.' })
      refresh()
    },
    onError: onMutationError,
  })
  const rowInterestedM = useMutation({
    mutationFn: (id: number) => leadMarkInterested(id),
    onSuccess: refresh,
    onError: onMutationError,
  })
  const rowRejectM = useMutation({
    mutationFn: (id: number) => leadReject(id),
    onSuccess: refresh,
    onError: onMutationError,
  })
  const rowSyncM = useMutation({
    mutationFn: (id: number) => leadSyncCrm(id),
    onSuccess: refresh,
    onError: onMutationError,
  })

  const columns = useMemo<ColumnDef<Lead, unknown>[]>(
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
            aria-label={`Select lead ${row.original.id}`}
            checked={selection.selected.includes(row.original.id)}
            onChange={(e) => selection.toggle(row.original.id, e.target.checked)}
          />
        ),
      },
      {
        accessorKey: 'full_name',
        header: 'Name',
        cell: ({ row }) => row.original.full_name || '—',
      },
      {
        accessorKey: 'company',
        header: 'Company',
        cell: ({ row }) => row.original.company || '—',
      },
      {
        accessorKey: 'email',
        header: 'Email',
        cell: ({ row }) => row.original.email || '—',
      },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => <StatusBadge status={row.original.status} kind="lead" />,
      },
      {
        id: 'actions',
        header: 'Actions',
        cell: ({ row }) => {
          const l = row.original
          return (
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" asChild>
                <Link to={`/leads/${l.id}`}>View</Link>
              </Button>
              <Button
                size="sm"
                disabled={l.status !== 'contacted' || rowInterestedM.isPending}
                onClick={() => rowInterestedM.mutate(l.id)}
              >
                Interested
              </Button>
              <Button
                size="sm"
                disabled={l.status !== 'interested' || rowSyncM.isPending}
                onClick={() => rowSyncM.mutate(l.id)}
              >
                Sync CRM
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={['rejected', 'synced'].includes(l.status) || rowRejectM.isPending}
                onClick={() => rowRejectM.mutate(l.id)}
              >
                Reject
              </Button>
            </div>
          )
        },
      },
    ],
    [items, selection, rowInterestedM, rowRejectM, rowSyncM]
  )

  return (
    <div className="space-y-4">
      <PageHeader
        title="Leads"
        description="Qualify converted prospects and sync interested leads to your CRM."
        actions={
          <>
            <Button variant="outline" asChild>
              <a href={leadsExportUrl()}>Export CSV</a>
            </Button>
            <Button disabled={!selection.canBulk || interestedM.isPending} onClick={() => interestedM.mutate()}>
              Mark interested
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
          placeholder="Search company, name, email…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="contacted">Contacted</option>
          <option value="interested">Interested</option>
          <option value="rejected">Rejected</option>
          <option value="synced">Synced</option>
        </Select>
        <Button variant="outline" onClick={() => void query.refetch()}>
          Refresh
        </Button>
      </div>

      <DataTable columns={columns} data={items} isLoading={query.isLoading} getRowId={(r) => String(r.id)} />

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
