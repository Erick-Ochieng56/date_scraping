import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { useEffect, useMemo, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link } from 'react-router-dom'
import { ExternalLink, RefreshCw, Sparkles, UserPlus } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { aiSearchFormSchema, type AiSearchFormValues } from '@/features/ai-search/schema'
import { getApiErrorMessage } from '@/shared/api/errors'
import {
  createAdminAiSearchJob,
  createAiSearchJob,
  getAdminAiSearchJob,
  getAiSearchJob,
  listAdminAiSearchJobs,
  listAdminUsers,
  listAiSearchJobs,
  promoteAdminAiSearchResult,
  promoteAiSearchResult,
} from '@/shared/api'
import type { AISearchJob, AISearchResult } from '@/shared/api/types'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { DataTable } from '@/shared/components/DataTable'
import { FormField } from '@/shared/components/FormField'
import { Input } from '@/shared/components/Input'
import { PageHeader } from '@/shared/components/PageHeader'
import { Select } from '@/shared/components/Select'
import { StatusBadge } from '@/shared/components/StatusBadge'

type Variant = 'staff' | 'admin'

export function AiSearchPage({ variant }: { variant: Variant }) {
  const qc = useQueryClient()
  const isAdmin = variant === 'admin'
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  const form = useForm<AiSearchFormValues>({
    defaultValues: {
      seedTopic: '',
      industry: '',
      region: 'Kenya Uganda Tanzania Rwanda Burundi South Sudan Ethiopia East Africa',
      delegateOwnerId: '',
    },
  })

  const usersQ = useQuery({
    queryKey: ['admin-users-ai-search'],
    queryFn: () => listAdminUsers({ page_size: 100 }),
    enabled: isAdmin,
  })

  const staffOptions = useMemo(() => {
    const items = usersQ.data?.items ?? []
    return items.filter((u) => u.role === 'staff' && u.is_active)
  }, [usersQ.data?.items])

  const jobsQ = useQuery({
    queryKey: ['ai-search-jobs', variant],
    queryFn: () => (isAdmin ? listAdminAiSearchJobs({ page_size: 25 }) : listAiSearchJobs({ page_size: 25 })),
  })

  const detailQ = useQuery({
    queryKey: ['ai-search-job', variant, selectedId],
    queryFn: () =>
      selectedId == null
        ? Promise.reject(new Error('no job'))
        : isAdmin
          ? getAdminAiSearchJob(selectedId, { page_size: 50 })
          : getAiSearchJob(selectedId, { page_size: 50 }),
    enabled: selectedId != null,
    refetchInterval: (q) => {
      const job = q.state.data?.job
      if (!job) return false
      if (['pending', 'generating', 'searching'].includes(job.status)) {
        const started = Date.parse(job.created_at)
        if (!Number.isNaN(started) && Date.now() - started > 12 * 60 * 1000) return 15_000
        return 3000
      }
      return false
    },
  })

  const selectedJob = detailQ.data?.job
  const jobAgeMs = useMemo(() => {
    if (!selectedJob?.created_at) return 0
    const t = Date.parse(selectedJob.created_at)
    return Number.isNaN(t) ? 0 : Date.now() - t
  }, [selectedJob?.created_at, detailQ.dataUpdatedAt])

  const pendingWorkerHint = Boolean(selectedJob?.status === 'pending' && jobAgeMs > 45_000)
  const longRunningHint = Boolean(
    selectedJob && ['generating', 'searching'].includes(selectedJob.status) && jobAgeMs > 4 * 60 * 1000
  )

  useEffect(() => {
    const st = selectedJob?.status
    if (st === 'done' || st === 'failed') {
      void qc.invalidateQueries({ queryKey: ['ai-search-jobs', variant] })
    }
  }, [selectedJob?.status, variant, qc])

  const createM = useMutation({
    mutationFn: (values: AiSearchFormValues) => {
      const ownerId =
        values.delegateOwnerId && values.delegateOwnerId.trim() !== ''
          ? Number(values.delegateOwnerId)
          : undefined
      if (isAdmin) {
        return createAdminAiSearchJob({
          seed_topic: values.seedTopic.trim(),
          industry: values.industry?.trim() || undefined,
          region: values.region?.trim() || undefined,
          ...(ownerId ? { owner_id: ownerId } : {}),
        })
      }
      return createAiSearchJob({
        seed_topic: values.seedTopic.trim(),
        industry: values.industry?.trim() || undefined,
        region: values.region?.trim() || undefined,
      })
    },
    onSuccess: (res) => {
      const job = res.data
      if (!res.success || !job) {
        setBanner({ error: res.error ?? 'Could not start job.' })
        return
      }
      setBanner({ message: `Job #${job.id} queued. Status: ${job.status}.` })
      form.reset()
      void qc.invalidateQueries({ queryKey: ['ai-search-jobs', variant] })
      setSelectedId(job.id)
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const promoteM = useMutation({
    mutationFn: (resultId: number) =>
      isAdmin ? promoteAdminAiSearchResult(resultId) : promoteAiSearchResult(resultId),
    onSuccess: (res) => {
      if (!res.success || !res.data) {
        setBanner({ error: res.error ?? 'Could not promote result.' })
        return
      }
      const label = res.data.created ? 'Created prospect' : 'Linked existing prospect'
      setBanner({ message: `${label} #${res.data.prospect_id}.` })
      void qc.invalidateQueries({ queryKey: ['ai-search-job', variant, selectedId] })
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const onSubmit = form.handleSubmit((raw) => {
    setBanner({})
    const parsed = aiSearchFormSchema.safeParse(raw)
    if (!parsed.success) {
      setBanner({ error: parsed.error.issues[0]?.message ?? 'Invalid form.' })
      return
    }
    createM.mutate(parsed.data)
  })

  const backHref = isAdmin ? '/admin/crawler' : '/crawler'
  const domainsHref = isAdmin ? '/admin/crawler/domains' : '/crawler/domains'
  const prospectsHref = isAdmin ? '/admin/pipeline' : '/prospects'

  const jobColumns = useMemo<ColumnDef<AISearchJob, unknown>[]>(
    () => [
      ...(isAdmin
        ? [
            {
              accessorKey: 'owner_username',
              header: 'Owner',
              cell: ({ row }: { row: { original: AISearchJob } }) =>
                row.original.owner_username ?? row.original.owner_id,
            } as ColumnDef<AISearchJob, unknown>,
          ]
        : []),
      { accessorKey: 'seed_topic', header: 'Topic' },
      {
        accessorKey: 'status',
        header: 'Status',
        cell: ({ row }) => <StatusBadge status={row.original.status} kind="generic" />,
      },
      { accessorKey: 'domains_discovered', header: 'Domains' },
      {
        id: 'actions',
        header: '',
        cell: ({ row }) => (
          <Button
            size="sm"
            variant={selectedId === row.original.id ? 'default' : 'outline'}
            onClick={() => setSelectedId(row.original.id)}
          >
            View
          </Button>
        ),
      },
    ],
    [isAdmin, selectedId]
  )

  const resultColumns = useMemo<ColumnDef<AISearchResult, unknown>[]>(
    () => [
      {
        accessorKey: 'domain',
        header: 'Domain',
        cell: ({ row }) => <span className="font-mono text-xs">{row.original.domain}</span>,
      },
      {
        accessorKey: 'source_url',
        header: 'Source page',
        cell: ({ row }) => {
          const url = row.original.source_url || `https://${row.original.domain}`
          return (
            <a className="line-clamp-2 text-info hover:underline" href={url} target="_blank" rel="noreferrer">
              {url}
            </a>
          )
        },
      },
      {
        id: 'score',
        header: 'Score',
        cell: ({ row }) => {
          const score = row.original.translation_need_score
          if (score == null) return <span className="text-muted-foreground">—</span>
          const warm = score >= 80 ? 'text-green-700 dark:text-green-400' : score >= 60 ? 'text-amber-700 dark:text-amber-400' : 'text-muted-foreground'
          return <span className={`font-mono text-sm font-medium ${warm}`}>{score}</span>
        },
      },
      {
        id: 'action_date',
        header: 'Date',
        cell: ({ row }) => {
          const d = row.original.action_date
          return d ? <span className="font-mono text-xs">{d}</span> : <span className="text-muted-foreground">—</span>
        },
      },
      {
        id: 'signal',
        header: 'Signal',
        cell: ({ row }) => row.original.buyer_signal_type || '—',
      },
      {
        id: 'evidence',
        header: 'Evidence',
        cell: ({ row }) => (
          <span className="max-w-[14rem] truncate text-xs text-muted-foreground" title={row.original.evidence_snippet || row.original.why_needs_translation}>
            {row.original.evidence_snippet || row.original.why_needs_translation || '—'}
          </span>
        ),
      },
      {
        id: 'org',
        header: 'Org',
        cell: ({ row }) => row.original.org_name || row.original.org_type || '—',
      },
      {
        accessorKey: 'why_needs_translation',
        header: 'Why translation',
        cell: ({ row }) => (
          <span className="max-w-xs truncate text-muted-foreground">{row.original.why_needs_translation || '—'}</span>
        ),
      },
      {
        id: 'actions',
        header: 'Actions',
        cell: ({ row }) => {
          const url = row.original.source_url || `https://${row.original.domain}`
          const prospectId = row.original.promoted_prospect_id
          const canPromote = row.original.promotable !== false
          return (
            <div className="flex items-center gap-1">
              <Button variant="ghost" size="sm" asChild>
                <a href={url} target="_blank" rel="noreferrer" title="Open source page">
                  <ExternalLink className="h-4 w-4" />
                </a>
              </Button>
              {prospectId ? (
                <Button variant="outline" size="sm" asChild>
                  <Link to={isAdmin ? prospectsHref : `${prospectsHref}/${prospectId}`}>
                    Prospect #{prospectId}
                  </Link>
                </Button>
              ) : (
                <Button
                  variant="outline"
                  size="sm"
                  disabled={promoteM.isPending || !canPromote}
                  onClick={() => promoteM.mutate(row.original.id)}
                  title={
                    canPromote
                      ? 'Create prospect from this result'
                      : 'Score below minimum for promotion (see server AI_SEARCH_PROMOTE_MIN_SCORE)'
                  }
                >
                  <UserPlus className="mr-1 h-4 w-4" />
                  Promote
                </Button>
              )}
            </div>
          )
        },
      },
    ],
    [isAdmin, promoteM.isPending, prospectsHref]
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="AI prospect search"
        description={
          isAdmin
            ? 'Serper finds buyer pages; Gemini scores each landing page for lead quality (score ≥ 60). Promote high-confidence results to prospects.'
            : 'Company-first Serper discovery plus Gemini page scoring. Only lead-worthy hits (score ≥ 60) are saved; promote them directly to your pipeline.'
        }
        actions={
          <>
            <Button variant="ghost" size="sm" asChild>
              <Link to={backHref}>← Back</Link>
            </Button>
            <Button variant="outline" size="sm" onClick={() => void jobsQ.refetch()} disabled={jobsQ.isFetching}>
              <RefreshCw className={`mr-2 h-4 w-4 ${jobsQ.isFetching ? 'animate-spin' : ''}`} />
              Refresh list
            </Button>
          </>
        }
      />

      <AlertBanner message={banner.message} error={banner.error} />

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="flex items-center gap-2 font-semibold text-foreground">
            <Sparkles className="h-5 w-5 text-amber-500" aria-hidden />
            Start a new search
          </h2>
          <form className="mt-3 space-y-3" onSubmit={onSubmit}>
            {isAdmin ? (
              <FormField
                label="Queue owner (optional)"
                htmlFor="delegate-owner"
                hint='Leave on "You" to run the search yourself. Pick a staff user to delegate queue ownership.'
              >
                <Select
                  id="delegate-owner"
                  {...form.register('delegateOwnerId')}
                  disabled={usersQ.isLoading}
                >
                  <option value="">You — use my account for discovered domains</option>
                  {staffOptions.map((u) => (
                    <option key={u.id} value={u.id}>
                      Staff: {u.username}
                      {u.email ? ` (${u.email})` : ''}
                    </option>
                  ))}
                </Select>
              </FormField>
            ) : null}
            <FormField label="Seed topic" htmlFor="seed-topic" error={form.formState.errors.seedTopic?.message}>
              <Input
                id="seed-topic"
                placeholder="e.g. international conferences East Africa 2026"
                {...form.register('seedTopic')}
              />
            </FormField>
            <div className="grid gap-3 sm:grid-cols-2">
              <FormField label="Industry (optional)" htmlFor="industry">
                <Input id="industry" placeholder="NGO, legal, medical…" {...form.register('industry')} />
              </FormField>
              <FormField label="Region" htmlFor="region">
                <Input
                  id="region"
                  placeholder="Defaults to East Africa when strict geo mode is on"
                  {...form.register('region')}
                />
              </FormField>
            </div>
            <Button type="submit" disabled={createM.isPending}>
              {createM.isPending ? 'Starting…' : 'Run AI search'}
            </Button>
          </form>
        </div>

        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="font-semibold text-foreground">Recent jobs</h2>
          <div className="mt-2">
            <DataTable
              columns={jobColumns}
              data={jobsQ.data?.items ?? []}
              isLoading={jobsQ.isLoading}
              emptyMessage="No jobs yet."
              getRowId={(r) => String(r.id)}
            />
          </div>
        </div>
      </div>

      {selectedId != null ? (
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold text-foreground">Job #{selectedId}</h2>
            <Button variant="outline" size="sm" onClick={() => void detailQ.refetch()} disabled={detailQ.isFetching}>
              Refresh detail
            </Button>
          </div>
          {detailQ.isLoading ? <p className="text-sm text-muted-foreground">Loading…</p> : null}
          {selectedJob ? (
            <div className="mb-4 space-y-1 text-sm">
              <p>
                <span className="text-muted-foreground">Status:</span>{' '}
                <StatusBadge status={selectedJob.status} kind="generic" />
              </p>
              {pendingWorkerHint ? (
                <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1.5 text-xs text-amber-950 dark:text-amber-100">
                  Still pending after ~1 minute. Start a Celery worker:{' '}
                  <code className="rounded bg-background/80 px-1">celery -A leads_app worker -l info</code>
                </p>
              ) : null}
              {longRunningHint ? (
                <p className="rounded-md border border-border bg-muted/50 px-2 py-1.5 text-xs text-muted-foreground">
                  This run is taking several minutes. The worker will mark the job failed if it exceeds the server time
                  limit (~5 minutes).
                </p>
              ) : null}
              {selectedJob.error_text ? <p className="text-destructive">{selectedJob.error_text}</p> : null}
              <p>
                <span className="text-muted-foreground">Domains discovered:</span> {selectedJob.domains_discovered}
              </p>
              {Array.isArray(selectedJob.queries_generated) && selectedJob.queries_generated.length > 0 ? (
                <details className="mt-2">
                  <summary className="cursor-pointer text-muted-foreground">Generated queries</summary>
                  <ul className="mt-1 list-inside list-disc text-xs">
                    {(selectedJob.queries_generated as { query?: string }[]).map((q, i) => (
                      <li key={i}>{typeof q === 'object' && q?.query ? q.query : JSON.stringify(q)}</li>
                    ))}
                  </ul>
                </details>
              ) : null}
            </div>
          ) : null}
          <DataTable
            columns={resultColumns}
            data={detailQ.data?.results.items ?? []}
            isLoading={detailQ.isLoading}
            emptyMessage="No results for this job yet."
            getRowId={(r) => String(r.id)}
          />
          <p className="mt-3 text-xs text-muted-foreground">
            Use <strong>Promote</strong> to add a verified result to{' '}
            <Link className="underline" to={prospectsHref}>
              prospects
            </Link>{' '}
            without waiting for crawl scoring. Queued domains also appear in the{' '}
            <Link className="underline" to={domainsHref}>
              crawler domain queue
            </Link>
            .
          </p>
        </div>
      ) : null}
    </div>
  )
}
