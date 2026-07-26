import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { classifyProspectSource, SOURCE_META } from '@/features/pipeline/evidence'
import { ProspectReviewFocus } from '@/features/pipeline/ProspectReviewFocus'
import { cn } from '@/lib/utils'
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
  listProspects,
  prospectConvert,
  prospectMarkContacted,
  prospectReject,
  prospectsBulkContacted,
  prospectsBulkConvert,
  prospectsBulkReject,
  prospectsExportUrl,
} from '@/shared/api/pipeline'
import type { PaginatedProspects, Prospect, ProspectSource } from '@/shared/api/types'
import { useRowSelection } from '@/shared/hooks/useRowSelection'
import { useServerList } from '@/shared/hooks/useServerList'

function fmtEventDate(v: string | null) {
  if (!v) return '—'
  return new Date(v).toLocaleDateString()
}

const SOURCE_FILTERS: { value: ProspectSource | ''; label: string }[] = [
  { value: '', label: 'All' },
  { value: 'ai_search', label: 'AI search' },
  { value: 'web_crawler', label: 'Web crawler' },
  { value: 'site_check', label: 'Site checks' },
]

export function ProspectsPage() {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState(searchParams.get('search') ?? '')
  const [status, setStatus] = useState(searchParams.get('status') ?? '')
  const [source, setSource] = useState<ProspectSource | ''>((searchParams.get('source') as ProspectSource) || '')
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})
  const [focusOpen, setFocusOpen] = useState(false)

  const selection = useRowSelection<Prospect['id']>((r) => r.id)

  const { items, total, page, pageSize, hasNext, goNext, goPrev, resetPage, query } = useServerList<
    Prospect,
    { status?: string; source?: ProspectSource },
    PaginatedProspects
  >({
    queryKey: ['prospects'],
    queryFn: listProspects,
    pageSize: 25,
    filters: { ...(status ? { status } : {}), ...(source ? { source } : {}) },
    search,
  })

  const sourceCounts = query.data?.source_counts
  const sourceTotal = sourceCounts ? sourceCounts.ai_search + sourceCounts.web_crawler + sourceCounts.site_check : 0

  useEffect(() => {
    const params = new URLSearchParams()
    if (status) params.set('status', status)
    if (source) params.set('source', source)
    if (search.trim()) params.set('search', search.trim())
    setSearchParams(params, { replace: true })
    resetPage()
  }, [status, source, search, setSearchParams, resetPage])

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
      setBanner({ message: 'Tracking selected prospects as leads.' })
      refresh()
    },
    onError: onMutationError,
  })
  const rejectM = useMutation({
    mutationFn: () => prospectsBulkReject(selection.selected),
    onSuccess: () => {
      setBanner({ message: 'Marked selected prospects as not relevant.' })
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
        id: 'source',
        header: 'Found by',
        cell: ({ row }) => {
          const src = classifyProspectSource(row.original.source_name)
          const meta = SOURCE_META[src]
          return (
            <span
              className={cn('inline-flex items-center rounded-full px-2.5 py-1 text-xs font-semibold', meta.softClass, meta.textClass)}
            >
              {meta.label}
            </span>
          )
        },
      },
      {
        id: 'actions',
        header: '',
        cell: ({ row }) => {
          const p = row.original
          return (
            <div className="flex items-center justify-end gap-1">
              <Button size="sm" variant="outline" asChild>
                <Link to={`/prospects/${p.id}`}>View</Link>
              </Button>
              <RowActionsMenu
                label={`More actions for ${p.company || p.event_name || 'prospect ' + p.id}`}
                actions={[
                  {
                    label: 'Mark contacted',
                    onSelect: () => rowContactM.mutate(p.id),
                    disabled: p.status !== 'new' || rowContactM.isPending,
                  },
                  {
                    label: 'Track as lead',
                    onSelect: () => rowConvertM.mutate(p.id),
                    disabled: !['new', 'contacted'].includes(p.status) || rowConvertM.isPending,
                  },
                  {
                    label: 'Not relevant',
                    onSelect: () => rowRejectM.mutate(p.id),
                    disabled: p.status === 'rejected' || rowRejectM.isPending,
                    destructive: true,
                  },
                ]}
              />
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
        title="Review queue"
        description="New organizations found by AI search, the web crawler, and site checks."
        actions={
          <>
            <Button onClick={() => setFocusOpen(true)}>Review one by one</Button>
            <Button variant="outline" asChild>
              <a href={prospectsExportUrl()}>Export CSV</a>
            </Button>
          </>
        }
      />

      <AlertBanner message={banner.message} error={banner.error} />

      <div className="flex flex-wrap gap-2">
        {SOURCE_FILTERS.map((f) => {
          const count = f.value === '' ? sourceTotal : (sourceCounts?.[f.value] ?? 0)
          const isActive = source === f.value
          return (
            <button
              key={f.value || 'all'}
              type="button"
              onClick={() => setSource(f.value)}
              aria-pressed={isActive}
              className={cn(
                'inline-flex items-center gap-1.5 rounded-full border px-3.5 py-1.5 text-sm font-semibold transition-colors',
                isActive
                  ? 'border-primary bg-primary text-primary-foreground'
                  : 'border-border bg-card text-muted-foreground hover:border-primary hover:text-primary'
              )}
            >
              {f.label}
              <span className={cn('tabular-nums', isActive ? 'opacity-80' : 'opacity-60')}>{count}</span>
            </button>
          )
        })}
      </div>

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

      {selection.canBulk ? (
        <div className="flex flex-wrap items-center gap-2 rounded-lg border border-primary/25 bg-primary/5 px-3 py-2">
          <span className="text-sm font-medium text-foreground">{selection.selected.length} selected</span>
          <Button size="sm" variant="outline" disabled={contactM.isPending} onClick={() => contactM.mutate()}>
            Mark contacted
          </Button>
          <Button size="sm" variant="outline" disabled={convertM.isPending} onClick={() => convertM.mutate()}>
            Track as leads
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
        errorMessage={query.isError ? getApiErrorMessage(query.error, 'Failed to load prospects.') : null}
        emptyMessage="Nothing to review yet. Try Find new leads to search for more prospects."
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

      <ProspectReviewFocus
        open={focusOpen}
        onClose={() => {
          setFocusOpen(false)
          refresh()
        }}
      />
    </div>
  )
}
