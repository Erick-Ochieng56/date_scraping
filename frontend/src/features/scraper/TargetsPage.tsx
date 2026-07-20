import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useEffect, useMemo, useState } from 'react'
import { Link, useSearchParams } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { filterTargets, hasItemSelector, targetTypeLabel } from '@/features/scraper/utils'
import { getApiErrorMessage } from '@/shared/api/errors'
import { listTargets, triggerTarget } from '@/shared/api/scraper'
import type { Target } from '@/shared/api/types'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { DataTable } from '@/shared/components/DataTable'
import { Input } from '@/shared/components/Input'
import { ListPagination } from '@/shared/components/ListPagination'
import { PageHeader } from '@/shared/components/PageHeader'
import { useDebouncedValue } from '@/shared/hooks/useDebouncedValue'

const PAGE_SIZE = 25

export function TargetsPage() {
  const qc = useQueryClient()
  const [searchParams, setSearchParams] = useSearchParams()
  const [search, setSearch] = useState(searchParams.get('search') ?? '')
  const [enabledOnly, setEnabledOnly] = useState(searchParams.get('enabled') === '1')
  const [page, setPage] = useState(1)
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  const debouncedSearch = useDebouncedValue(search)

  const targetsQ = useQuery({
    queryKey: ['targets', enabledOnly],
    queryFn: () => listTargets({ page_size: 200, enabled: enabledOnly ? true : undefined }),
  })

  useEffect(() => {
    const params = new URLSearchParams()
    if (debouncedSearch.trim()) params.set('search', debouncedSearch.trim())
    if (enabledOnly) params.set('enabled', '1')
    setSearchParams(params, { replace: true })
    setPage(1)
  }, [debouncedSearch, enabledOnly, setSearchParams])

  const filtered = useMemo(
    () => filterTargets(targetsQ.data?.items ?? [], debouncedSearch),
    [targetsQ.data?.items, debouncedSearch]
  )

  const total = filtered.length
  const pageItems = filtered.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE)
  const hasNext = page * PAGE_SIZE < total

  const triggerOneM = useMutation({
    mutationFn: (targetId: number) => triggerTarget(targetId),
    onSuccess: (data) => {
      setBanner({ message: data.message ?? 'Scrape queued.' })
      void qc.invalidateQueries({ queryKey: ['targets'] })
      void qc.invalidateQueries({ queryKey: ['scrape-runs'] })
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err, 'Could not start scrape.') }),
  })

  const columns = useMemo<ColumnDef<Target, unknown>[]>(
    () => [
      {
        accessorKey: 'name',
        header: 'Name',
        cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
      },
      {
        accessorKey: 'target_type',
        header: 'Engine',
        cell: ({ row }) => targetTypeLabel(row.original.target_type),
      },
      {
        accessorKey: 'start_url',
        header: 'Start URL',
        cell: ({ row }) => (
          <a
            className="block max-w-[200px] break-all text-primary underline-offset-4 hover:underline"
            href={row.original.start_url}
            target="_blank"
            rel="noreferrer"
          >
            {row.original.start_url}
          </a>
        ),
      },
      {
        id: 'selectors',
        header: 'Selectors',
        cell: ({ row }) =>
          hasItemSelector(row.original.config) ? (
            <span className="rounded bg-muted px-2 py-0.5 text-xs">Ready</span>
          ) : (
            <span className="text-xs text-amber-700 dark:text-amber-400">Needs config</span>
          ),
      },
      {
        accessorKey: 'enabled',
        header: 'Enabled',
        cell: ({ row }) => (row.original.enabled ? 'Yes' : 'No'),
      },
      {
        accessorKey: 'run_every_minutes',
        header: 'Schedule',
        cell: ({ row }) => <span className="whitespace-nowrap">Every {row.original.run_every_minutes} min</span>,
      },
      {
        accessorKey: 'last_run_at',
        header: 'Last run',
        cell: ({ row }) => (
          <span className="whitespace-nowrap">
            {row.original.last_run_at ? new Date(row.original.last_run_at).toLocaleString() : '—'}
          </span>
        ),
      },
      {
        id: 'actions',
        header: 'Actions',
        cell: ({ row }) => {
          const target = row.original
          return (
            <div className="flex flex-wrap gap-2">
              <Button size="sm" variant="outline" asChild>
                <Link to={`/targets/${target.id}`}>Configure</Link>
              </Button>
              <Button
                size="sm"
                disabled={triggerOneM.isPending}
                onClick={() => {
                  setBanner({})
                  triggerOneM.mutate(target.id)
                }}
              >
                Scrape now
              </Button>
              <Button size="sm" variant="ghost" className="h-8 px-2" asChild>
                <Link to={`/runs?target_id=${target.id}`}>Runs</Link>
              </Button>
            </div>
          )
        },
      },
    ],
    [triggerOneM]
  )

  return (
    <div className="space-y-4">
      <PageHeader
        title="Scrape targets"
        description="Each target is one listing page (URL + CSS selectors). Configure selectors, then run scrapes manually — there is no “scrape all” for staff."
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to="/targets/new?mode=manual">Manual setup</Link>
            </Button>
            <Button asChild>
              <Link to="/targets/new">Add target</Link>
            </Button>
          </>
        }
      />

      <AlertBanner message={banner.message} error={banner.error} />

      <div className="flex flex-wrap gap-2">
        <Input
          className="min-w-[280px] flex-1"
          placeholder="Search name, type, or URL…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <label className="inline-flex h-9 items-center gap-2 rounded-md border border-border px-3 text-sm">
          <input
            type="checkbox"
            checked={enabledOnly}
            onChange={(e) => setEnabledOnly(e.target.checked)}
          />
          Enabled only
        </label>
        <Button variant="outline" onClick={() => void targetsQ.refetch()}>
          Refresh
        </Button>
      </div>

      <DataTable
        columns={columns}
        data={pageItems}
        isLoading={targetsQ.isLoading}
        errorMessage={targetsQ.isError ? getApiErrorMessage(targetsQ.error, 'Failed to load targets.') : null}
        emptyMessage="No targets match your filters."
        getRowId={(r) => String(r.id)}
      />

      <ListPagination
        page={page}
        pageSize={PAGE_SIZE}
        total={total}
        hasNext={hasNext}
        onPrev={() => setPage((p) => Math.max(1, p - 1))}
        onNext={() => setPage((p) => p + 1)}
        isLoading={targetsQ.isFetching}
      />
    </div>
  )
}
