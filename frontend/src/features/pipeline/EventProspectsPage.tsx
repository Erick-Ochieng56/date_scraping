import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useEffect, useMemo, useState } from 'react'
import { Link, useNavigate, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { getApiErrorMessage } from '@/shared/api/errors'
import {
  listEventProspects,
  promoteEventProspect,
  rejectEventProspect,
  type EventProspectListParams,
} from '@/shared/api/eventProspects'
import type { EventProspect } from '@/shared/api/types'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { DataTable } from '@/shared/components/DataTable'
import { Input } from '@/shared/components/Input'
import { ListPagination } from '@/shared/components/ListPagination'
import { PageHeader } from '@/shared/components/PageHeader'
import { ScoreBadge } from '@/shared/components/ScoreBadge'
import { Select } from '@/shared/components/Select'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { useServerList } from '@/shared/hooks/useServerList'

type EventProspectFilters = Pick<EventProspectListParams, 'status' | 'min_score' | 'sort'>

function fmtDate(value: string | null) {
  if (!value) return '—'
  const d = new Date(value)
  return Number.isNaN(d.getTime()) ? value : d.toLocaleDateString()
}

function joinList(items: string[]) {
  return items?.length ? items.slice(0, 4).join(', ') : '—'
}

export function EventProspectsPage() {
  const qc = useQueryClient()
  const navigate = useNavigate()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState(searchParams.get('search') ?? '')
  const [status, setStatus] = useState(searchParams.get('status') ?? 'new')
  const [minScore, setMinScore] = useState(searchParams.get('min_score') ?? '')
  const [sort, setSort] = useState<'urgency' | 'date' | 'score'>(
    (searchParams.get('sort') as EventProspectFilters['sort']) || 'urgency'
  )
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  const filters = useMemo<EventProspectFilters>(() => {
    const f: EventProspectFilters = { sort }
    if (status) f.status = status
    const parsedMin = parseInt(minScore, 10)
    if (!Number.isNaN(parsedMin)) f.min_score = parsedMin
    return f
  }, [status, minScore, sort])

  const { items, total, page, pageSize, hasNext, goNext, goPrev, resetPage, query } = useServerList<
    EventProspect,
    EventProspectFilters
  >({
    queryKey: ['event-prospects'],
    queryFn: listEventProspects,
    pageSize: 25,
    filters,
    search,
  })

  useEffect(() => {
    const params = new URLSearchParams()
    if (status) params.set('status', status)
    if (search.trim()) params.set('search', search.trim())
    if (minScore.trim()) params.set('min_score', minScore.trim())
    if (sort !== 'urgency') params.set('sort', sort)
    setSearchParams(params, { replace: true })
    resetPage()
  }, [status, search, minScore, sort, setSearchParams, resetPage])

  const refresh = () => {
    setBanner({})
    void qc.invalidateQueries({ queryKey: ['event-prospects'] })
    void qc.invalidateQueries({ queryKey: ['prospects'] })
  }

  const onError = (err: unknown) => setBanner({ error: getApiErrorMessage(err) })

  const promoteM = useMutation({
    mutationFn: (id: number) => promoteEventProspect(id),
    onSuccess: (res) => {
      setBanner({ message: res.created ? 'Promoted to new prospect.' : 'Linked to existing prospect.' })
      refresh()
      if (res.prospect_id) navigate(`/prospects/${res.prospect_id}`)
    },
    onError,
  })

  const rejectM = useMutation({
    mutationFn: (id: number) => rejectEventProspect(id),
    onSuccess: () => {
      setBanner({ message: 'Marked event as irrelevant.' })
      refresh()
    },
    onError,
  })

  const columns = useMemo<ColumnDef<EventProspect, unknown>[]>(
    () => [
      {
        accessorKey: 'urgency_score',
        header: 'Urgency',
        cell: ({ row }) => <span className="tabular-nums font-medium">{row.original.urgency_score}</span>,
      },
      {
        accessorKey: 'translation_need_score',
        header: 'Score',
        cell: ({ row }) => <ScoreBadge score={row.original.translation_need_score} />,
      },
      {
        accessorKey: 'event_name',
        header: 'Event',
        cell: ({ row }) => (
          <div className="max-w-xs">
            <p className="font-medium">{row.original.event_name}</p>
            <p className="text-xs text-muted-foreground">{row.original.organizer_name || row.original.organizer_domain}</p>
          </div>
        ),
      },
      {
        id: 'event_date',
        header: 'Date',
        cell: ({ row }) => fmtDate(row.original.event_date) || row.original.event_date_raw || '—',
      },
      {
        id: 'languages',
        header: 'Languages',
        cell: ({ row }) => joinList(row.original.languages_involved),
      },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => <StatusBadge status={row.original.status} kind="generic" />,
      },
      {
        id: 'actions',
        header: 'Actions',
        cell: ({ row }) => {
          const ep = row.original
          const canAct = !['converted', 'expired', 'irrelevant'].includes(ep.status)
          return (
            <div className="flex flex-wrap gap-2">
              {ep.event_url ? (
                <Button size="sm" variant="outline" asChild>
                  <a href={ep.event_url} target="_blank" rel="noreferrer">
                    Event
                  </a>
                </Button>
              ) : null}
              <Button
                size="sm"
                disabled={!canAct || promoteM.isPending}
                onClick={() => promoteM.mutate(ep.id)}
              >
                Promote
              </Button>
              <Button
                size="sm"
                variant="outline"
                disabled={!canAct || rejectM.isPending}
                onClick={() => rejectM.mutate(ep.id)}
              >
                Irrelevant
              </Button>
            </div>
          )
        },
      },
    ],
    [promoteM, rejectM]
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Event prospects"
        description="Upcoming events discovered during crawls — sorted by urgency and translation need."
        actions={
          <Button variant="outline" asChild>
            <Link to="/prospects">View pipeline prospects</Link>
          </Button>
        }
      />

      <AlertBanner message={banner.message} error={banner.error} />

      <div className="flex flex-wrap gap-2">
        <Input
          className="min-w-[200px] flex-1"
          placeholder="Search event, organizer, location…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <Select value={status} onChange={(e) => setStatus(e.target.value)}>
          <option value="">All statuses</option>
          <option value="new">New</option>
          <option value="contacted">Contacted</option>
          <option value="qualified">Qualified</option>
          <option value="converted">Converted</option>
          <option value="expired">Expired</option>
          <option value="irrelevant">Irrelevant</option>
        </Select>
        <Input
          className="w-28"
          type="number"
          min={0}
          max={100}
          placeholder="Min score"
          value={minScore}
          onChange={(e) => setMinScore(e.target.value)}
        />
        <Select
          value={sort}
          onChange={(e) => {
            const v = e.target.value
            if (v === 'urgency' || v === 'score' || v === 'date') setSort(v)
          }}
        >
          <option value="urgency">Urgency</option>
          <option value="score">Translation score</option>
          <option value="date">Event date</option>
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
