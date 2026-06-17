import { useQuery } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { adminKeys } from '@/features/admin/queryKeys'
import { fmtDate } from '@/features/admin/utils'
import { fetchMetricsSummary } from '@/shared/api/metrics'
import { leadsExportUrl, listLeads, listProspects, prospectsExportUrl } from '@/shared/api/pipeline'
import type { Lead, Prospect } from '@/shared/api/types'
import { DataTable } from '@/shared/components/DataTable'
import { Input } from '@/shared/components/Input'
import { ListPagination } from '@/shared/components/ListPagination'
import { PageHeader } from '@/shared/components/PageHeader'
import { Select } from '@/shared/components/Select'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { useServerList } from '@/shared/hooks/useServerList'

type PipelineTab = 'prospects' | 'leads'

const PROSPECT_STATUSES = ['', 'new', 'contacted', 'converted', 'rejected'] as const
const LEAD_STATUSES = ['', 'contacted', 'interested', 'synced', 'rejected'] as const

export function AdminPipelinePage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const initialTab = searchParams.get('tab') === 'leads' ? 'leads' : 'prospects'
  const [tab, setTab] = useState<PipelineTab>(initialTab)
  const [search, setSearch] = useState(searchParams.get('search') ?? '')
  const [status, setStatus] = useState(searchParams.get('status') ?? '')

  const metricsQ = useQuery({
    queryKey: adminKeys.pipeline.metrics,
    queryFn: fetchMetricsSummary,
  })

  const prospectFilters = useMemo(() => (status ? { status } : {}), [status])
  const leadFilters = useMemo(() => (status ? { status } : {}), [status])

  const prospectsList = useServerList<Prospect, { status?: string }>({
    queryKey: ['admin', 'pipeline', 'prospects'],
    queryFn: listProspects,
    pageSize: 25,
    filters: prospectFilters,
    search,
    enabled: tab === 'prospects',
  })

  const leadsList = useServerList<Lead, { status?: string }>({
    queryKey: ['admin', 'pipeline', 'leads'],
    queryFn: listLeads,
    pageSize: 25,
    filters: leadFilters,
    search,
    enabled: tab === 'leads',
  })

  const { items: prospectItems, total: prospectTotal, page: prospectPage, pageSize, hasNext: prospectHasNext, goNext: prospectGoNext, goPrev: prospectGoPrev, resetPage: resetProspectsPage, query: prospectsQuery } = prospectsList
  const { items: leadItems, total: leadTotal, page: leadPage, hasNext: leadHasNext, goNext: leadGoNext, goPrev: leadGoPrev, resetPage: resetLeadsPage, query: leadsQuery } = leadsList

  useEffect(() => {
    const params = new URLSearchParams()
    params.set('tab', tab)
    if (status) params.set('status', status)
    if (search.trim()) params.set('search', search.trim())
    setSearchParams(params, { replace: true })
    resetProspectsPage()
    resetLeadsPage()
  }, [tab, status, search, setSearchParams, resetProspectsPage, resetLeadsPage])

  const prospectColumns = useMemo<ColumnDef<Prospect, unknown>[]>(
    () => [
      { accessorKey: 'company', header: 'Company', cell: ({ row }) => row.original.company || '—' },
      { accessorKey: 'event_name', header: 'Event', cell: ({ row }) => row.original.event_name || '—' },
      { accessorKey: 'email', header: 'Email', cell: ({ row }) => row.original.email || '—' },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => <StatusBadge status={row.original.status} kind="prospect" />,
      },
      {
        accessorKey: 'created_at',
        header: 'Created',
        cell: ({ row }) => fmtDate(row.original.created_at),
      },
    ],
    []
  )

  const leadColumns = useMemo<ColumnDef<Lead, unknown>[]>(
    () => [
      { accessorKey: 'full_name', header: 'Name', cell: ({ row }) => row.original.full_name || '—' },
      { accessorKey: 'company', header: 'Company', cell: ({ row }) => row.original.company || '—' },
      { accessorKey: 'email', header: 'Email', cell: ({ row }) => row.original.email || '—' },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => <StatusBadge status={row.original.status} kind="lead" />,
      },
      {
        accessorKey: 'created_at',
        header: 'Created',
        cell: ({ row }) => fmtDate(row.original.created_at),
      },
    ],
    []
  )

  const m = metricsQ.data

  return (
    <div className="space-y-6">
      <PageHeader
        title="Pipeline oversight"
        description="Cross-user prospect and lead volumes. Superuser accounts see all records; use Users to transfer ownership when needed."
        actions={
          <div className="flex flex-wrap gap-2">
            <Button variant="outline" asChild>
              <a href={prospectsExportUrl()}>Export prospects CSV</a>
            </Button>
            <Button variant="outline" asChild>
              <a href={leadsExportUrl()}>Export leads CSV</a>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/admin/users">Manage users</Link>
            </Button>
          </div>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">New prospects</p>
          <p className="text-2xl font-semibold">{m?.prospects_new ?? '—'}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Contacted prospects</p>
          <p className="text-2xl font-semibold">{m?.prospects_contacted ?? '—'}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Interested leads</p>
          <p className="text-2xl font-semibold">{m?.leads_interested ?? '—'}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Synced to CRM</p>
          <p className="text-2xl font-semibold">{m?.leads_synced ?? '—'}</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-1 border-b border-border pb-2">
        <Button
          size="sm"
          variant={tab === 'prospects' ? 'secondary' : 'ghost'}
          onClick={() => {
            setTab('prospects')
            setStatus('')
          }}
        >
          Prospects
        </Button>
        <Button
          size="sm"
          variant={tab === 'leads' ? 'secondary' : 'ghost'}
          onClick={() => {
            setTab('leads')
            setStatus('')
          }}
        >
          Leads
        </Button>
      </div>

      <div className="flex flex-wrap gap-2">
        <Input
          className="min-w-[240px] flex-1"
          placeholder={tab === 'prospects' ? 'Search company, event, email…' : 'Search name, company, email…'}
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          {tab === 'prospects'
            ? PROSPECT_STATUSES.filter(Boolean).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))
            : LEAD_STATUSES.filter(Boolean).map((s) => (
                <option key={s} value={s}>
                  {s}
                </option>
              ))}
        </Select>
        <Button variant="outline" onClick={() => void (tab === 'prospects' ? prospectsQuery : leadsQuery).refetch()}>
          Refresh
        </Button>
      </div>

      {tab === 'prospects' ? (
        <DataTable
          columns={prospectColumns}
          data={prospectItems}
          isLoading={prospectsQuery.isLoading}
          emptyMessage="No prospects match your filters."
          getRowId={(r) => String(r.id)}
        />
      ) : (
        <DataTable
          columns={leadColumns}
          data={leadItems}
          isLoading={leadsQuery.isLoading}
          emptyMessage="No leads match your filters."
          getRowId={(r) => String(r.id)}
        />
      )}

      <ListPagination
        page={tab === 'prospects' ? prospectPage : leadPage}
        pageSize={pageSize}
        total={tab === 'prospects' ? prospectTotal : leadTotal}
        hasNext={tab === 'prospects' ? prospectHasNext : leadHasNext}
        onPrev={tab === 'prospects' ? prospectGoPrev : leadGoPrev}
        onNext={tab === 'prospects' ? prospectGoNext : leadGoNext}
        isLoading={tab === 'prospects' ? prospectsQuery.isFetching : leadsQuery.isFetching}
      />
    </div>
  )
}
