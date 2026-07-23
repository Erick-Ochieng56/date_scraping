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
import { RowActionsMenu } from '@/shared/components/RowActionsMenu'
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
      setBanner({ message: 'Marked selected leads as not relevant.' })
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
        header: '',
        cell: ({ row }) => {
          const l = row.original
          return (
            <div className="flex items-center justify-end gap-1">
              <Button size="sm" variant="outline" asChild>
                <Link to={`/leads/${l.id}`}>View</Link>
              </Button>
              <RowActionsMenu
                label={`More actions for ${l.full_name || l.company || 'lead ' + l.id}`}
                actions={[
                  {
                    label: 'Mark interested',
                    onSelect: () => rowInterestedM.mutate(l.id),
                    disabled: l.status !== 'contacted' || rowInterestedM.isPending,
                  },
                  {
                    label: 'Sync to CRM',
                    onSelect: () => rowSyncM.mutate(l.id),
                    disabled: l.status !== 'interested' || rowSyncM.isPending,
                  },
                  {
                    label: 'Not relevant',
                    onSelect: () => rowRejectM.mutate(l.id),
                    disabled: ['rejected', 'synced'].includes(l.status) || rowRejectM.isPending,
                    destructive: true,
                  },
                ]}
              />
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
        title="My leads"
        description="Prospects you're pursuing — contacted, interested, and synced to the CRM."
        actions={
          <Button variant="outline" asChild>
            <a href={leadsExportUrl()}>Export CSV</a>
          </Button>
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

      {selection.canBulk ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/25 bg-primary/5 px-3 py-2">
          <span className="text-sm font-medium text-foreground">{selection.selected.length} selected</span>
          <Button size="sm" variant="outline" disabled={interestedM.isPending} onClick={() => interestedM.mutate()}>
            Mark interested
          </Button>
          <Button size="sm" variant="destructive" disabled={rejectM.isPending} onClick={() => rejectM.mutate()}>
            Not relevant
          </Button>
        </div>
      ) : null}

      <DataTable
        columns={columns}
        data={items}
        isLoading={query.isLoading}
        errorMessage={query.isError ? getApiErrorMessage(query.error, 'Failed to load leads.') : null}
        emptyMessage="No leads yet. Track a prospect from the review queue to see it here."
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
