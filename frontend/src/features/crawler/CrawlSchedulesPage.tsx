import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { Plus, Trash2 } from 'lucide-react'
import { useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import { crawlerKeys, invalidateCrawlerQueries } from '@/features/crawler/queryKeys'
import { getApiErrorMessage } from '@/shared/api/errors'
import {
  createCrawlSchedule,
  deleteCrawlSchedule,
  listCrawlSchedules,
  updateCrawlSchedule,
} from '@/shared/api/crawler'
import type { CrawlSchedule } from '@/shared/api/types'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { DataTable } from '@/shared/components/DataTable'
import { Input } from '@/shared/components/Input'
import { ListPagination } from '@/shared/components/ListPagination'
import { PageHeader } from '@/shared/components/PageHeader'
import { Select } from '@/shared/components/Select'
import { StatusBadge } from '@/shared/components/StatusBadge'
import { useServerList } from '@/shared/hooks/useServerList'

const INTERVAL_OPTIONS = [
  { value: '60', label: 'Every 1 hour' },
  { value: '360', label: 'Every 6 hours' },
  { value: '720', label: 'Every 12 hours' },
  { value: '1440', label: 'Every 24 hours' },
  { value: '10080', label: 'Every 7 days' },
] as const

const SESSION_DURATION_OPTIONS = [
  { value: '', label: 'Default (6 hours)' },
  { value: '60', label: '1 hour per run' },
  { value: '180', label: '3 hours per run' },
  { value: '360', label: '6 hours per run' },
  { value: '720', label: '12 hours per run' },
] as const

function formatMinutes(minutes: number | null | undefined): string {
  if (!minutes) return 'Default'
  if (minutes % 1440 === 0) return `${minutes / 1440}d`
  if (minutes % 60 === 0) return `${minutes / 60}h`
  return `${minutes}m`
}

function formatDateTime(iso: string | null | undefined): string {
  if (!iso) return '—'
  return new Date(iso).toLocaleString()
}

export function CrawlSchedulesPage() {
  const qc = useQueryClient()
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})
  const [name, setName] = useState('')
  const [intervalMinutes, setIntervalMinutes] = useState('720')
  const [sessionDuration, setSessionDuration] = useState('')

  const { items, total, page, pageSize, hasNext, goNext, goPrev, query } = useServerList<CrawlSchedule>({
    queryKey: ['crawler', 'schedules'],
    queryFn: listCrawlSchedules,
    pageSize: 25,
    refetchInterval: 30_000,
  })

  const createM = useMutation({
    mutationFn: () =>
      createCrawlSchedule({
        name: name.trim(),
        enabled: true,
        interval_minutes: Number.parseInt(intervalMinutes, 10),
        session_duration_minutes: sessionDuration ? Number.parseInt(sessionDuration, 10) : null,
      }),
    onSuccess: () => {
      setBanner({ message: 'Schedule created.' })
      setName('')
      invalidateCrawlerQueries(qc)
      void qc.invalidateQueries({ queryKey: crawlerKeys.schedules({}) })
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const toggleM = useMutation({
    mutationFn: ({ id, enabled }: { id: number; enabled: boolean }) => updateCrawlSchedule(id, { enabled }),
    onSuccess: () => {
      invalidateCrawlerQueries(qc)
      void qc.invalidateQueries({ queryKey: ['crawler', 'schedules'] })
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const deleteM = useMutation({
    mutationFn: (id: number) => deleteCrawlSchedule(id),
    onSuccess: () => {
      setBanner({ message: 'Schedule deleted.' })
      invalidateCrawlerQueries(qc)
      void qc.invalidateQueries({ queryKey: ['crawler', 'schedules'] })
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const columns = useMemo<ColumnDef<CrawlSchedule, unknown>[]>(
    () => [
      {
        accessorKey: 'name',
        header: 'Name',
        cell: ({ row }) => <span className="font-medium">{row.original.name}</span>,
      },
      {
        accessorKey: 'interval_minutes',
        header: 'Interval',
        cell: ({ row }) => formatMinutes(row.original.interval_minutes),
      },
      {
        accessorKey: 'session_duration_minutes',
        header: 'Session length',
        cell: ({ row }) => formatMinutes(row.original.session_duration_minutes),
      },
      {
        accessorKey: 'enabled',
        header: 'Status',
        cell: ({ row }) => {
          const label = row.original.enabled
            ? row.original.is_due
              ? 'Due'
              : 'Active'
            : 'Disabled'
          return <StatusBadge status={label} />
        },
      },
      {
        accessorKey: 'last_started_at',
        header: 'Last started',
        cell: ({ row }) => formatDateTime(row.original.last_started_at),
      },
      {
        accessorKey: 'next_run_at',
        header: 'Next run',
        cell: ({ row }) => (row.original.enabled ? formatDateTime(row.original.next_run_at) : '—'),
      },
      {
        id: 'actions',
        header: 'Actions',
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-2">
            <Button
              size="sm"
              variant="outline"
              disabled={toggleM.isPending}
              onClick={() =>
                toggleM.mutate({ id: row.original.id, enabled: !row.original.enabled })
              }
            >
              {row.original.enabled ? 'Disable' : 'Enable'}
            </Button>
            <Button
              size="sm"
              variant="outline"
              disabled={deleteM.isPending}
              onClick={() => {
                const ok = window.confirm(`Delete schedule "${row.original.name}"?`)
                if (ok) deleteM.mutate(row.original.id)
              }}
            >
              <Trash2 className="size-3.5" aria-hidden />
              Delete
            </Button>
          </div>
        ),
      },
    ],
    [deleteM, toggleM]
  )

  const handleCreate = () => {
    if (!name.trim()) {
      setBanner({ error: 'Enter a schedule name.' })
      return
    }
    createM.mutate()
  }

  return (
    <div className="space-y-6">
      <PageHeader
        title="Crawl schedules"
        description="Recurring crawl sessions start automatically when due and no session is already running."
      />

      <AlertBanner message={banner.message} error={banner.error} />

      <section className="space-y-3 rounded-lg border border-border bg-card p-4">
        <h2 className="text-sm font-medium text-foreground">New schedule</h2>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <Input
            placeholder="Schedule name"
            value={name}
            onChange={(e) => setName(e.target.value)}
            aria-label="Schedule name"
          />
          <Select
            value={intervalMinutes}
            onChange={(e) => setIntervalMinutes(e.target.value)}
            aria-label="Run interval"
          >
            {INTERVAL_OPTIONS.map((opt) => (
              <option key={opt.value} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </Select>
          <Select
            value={sessionDuration}
            onChange={(e) => setSessionDuration(e.target.value)}
            aria-label="Session duration"
          >
            {SESSION_DURATION_OPTIONS.map((opt) => (
              <option key={opt.value || 'default'} value={opt.value}>
                {opt.label}
              </option>
            ))}
          </Select>
          <Button disabled={createM.isPending} onClick={handleCreate}>
            <Plus className="size-4" aria-hidden />
            {createM.isPending ? 'Creating…' : 'Create schedule'}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          Schedules are checked every few minutes. A new session starts only when the interval has elapsed and you have
          no active crawl session.
        </p>
      </section>

      <DataTable
        columns={columns}
        data={items}
        isLoading={query.isLoading}
        emptyMessage="No schedules yet. Create one above to automate crawl sessions."
      />

      <ListPagination
        page={page}
        pageSize={pageSize}
        total={total}
        hasNext={hasNext}
        onPrev={goPrev}
        onNext={goNext}
      />
    </div>
  )
}
