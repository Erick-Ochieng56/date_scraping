import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { prospectActionColumns, prospectBaseColumns } from '@/features/pipeline/prospectColumns'
import { Button } from '@/components/ui/button'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { DataTable } from '@/shared/components/DataTable'
import { Input } from '@/shared/components/Input'
import { ListPagination } from '@/shared/components/ListPagination'
import { PageHeader } from '@/shared/components/PageHeader'
import { Select } from '@/shared/components/Select'
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
  type ProspectListParams,
} from '@/shared/api/pipeline'
import type { Prospect } from '@/shared/api/types'
import { useRowSelection } from '@/shared/hooks/useRowSelection'
import { useServerList } from '@/shared/hooks/useServerList'

type ProspectFilters = Pick<ProspectListParams, 'status' | 'source' | 'min_score' | 'sort'>

export function ProspectsPage() {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState(searchParams.get('search') ?? '')
  const [status, setStatus] = useState(searchParams.get('status') ?? '')
  const [source, setSource] = useState(searchParams.get('source') ?? '')
  const [minScore, setMinScore] = useState(searchParams.get('min_score') ?? '')
  const [sort, setSort] = useState<'created_at' | 'score'>(
    searchParams.get('sort') === 'score' ? 'score' : 'created_at'
  )
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  const selection = useRowSelection<Prospect['id']>((r) => r.id)

  const filters = useMemo<ProspectFilters>(() => {
    const f: ProspectFilters = { sort }
    if (status) f.status = status
    if (source.trim()) f.source = source.trim()
    const parsedMin = parseInt(minScore, 10)
    if (!Number.isNaN(parsedMin)) f.min_score = parsedMin
    return f
  }, [status, source, minScore, sort])

  const { items, total, page, pageSize, hasNext, goNext, goPrev, resetPage, query, debouncedSearch } = useServerList<
    Prospect,
    ProspectFilters
  >({
    queryKey: ['prospects'],
    queryFn: listProspects,
    pageSize: 25,
    filters,
    search,
  })

  useEffect(() => {
    const params = new URLSearchParams()
    if (status) params.set('status', status)
    if (search.trim()) params.set('search', search.trim())
    if (source.trim()) params.set('source', source.trim())
    if (minScore.trim()) params.set('min_score', minScore.trim())
    if (sort === 'score') params.set('sort', 'score')
    setSearchParams(params, { replace: true })
    resetPage()
  }, [status, search, source, minScore, sort, setSearchParams, resetPage])

  const exportHref = useMemo(
    () =>
      prospectsExportUrl({
        status: status || undefined,
        search: debouncedSearch || undefined,
        source: source.trim() || undefined,
        min_score: filters.min_score,
      }),
    [status, debouncedSearch, source, filters.min_score]
  )

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
      ...prospectBaseColumns(),
      ...prospectActionColumns({
        onContact: (id) => rowContactM.mutate(id),
        onConvert: (id) => rowConvertM.mutate(id),
        onReject: (id) => rowRejectM.mutate(id),
        contactPending: rowContactM.isPending,
        convertPending: rowConvertM.isPending,
        rejectPending: rowRejectM.isPending,
      }),
    ],
    [items, selection, rowContactM, rowConvertM, rowRejectM]
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Prospects"
        description="Review discoveries by score and source. Sort by score to work the highest-quality contacts first."
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to="/prospects/new">Add prospect</Link>
            </Button>
            <Button variant="outline" asChild>
              <a href={exportHref}>Export CSV</a>
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
          className="min-w-[200px] flex-1"
          placeholder="Search company, event, email, source…"
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
        <Input
          className="w-36"
          placeholder="Source"
          value={source}
          onChange={(e) => setSource(e.target.value)}
        />
        <Input
          className="w-28"
          type="number"
          min={0}
          max={100}
          placeholder="Min score"
          value={minScore}
          onChange={(e) => setMinScore(e.target.value)}
        />
        <Select value={sort} onChange={(e) => setSort(e.target.value as 'created_at' | 'score')}>
          <option value="created_at">Newest first</option>
          <option value="score">Highest score</option>
        </Select>
        <Button variant="outline" onClick={() => void query.refetch()}>
          Refresh
        </Button>
        {sort !== 'score' || minScore !== '60' || status !== 'new' ? (
          <Button
            variant="ghost"
            onClick={() => {
              setSort('score')
              setMinScore('60')
              setStatus('new')
            }}
          >
            Priority queue
          </Button>
        ) : null}
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
