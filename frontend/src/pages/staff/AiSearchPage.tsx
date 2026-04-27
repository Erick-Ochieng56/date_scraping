import { useEffect, useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ExternalLink, RefreshCw, Sparkles } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  createAdminAiSearchJob,
  createAiSearchJob,
  getAdminAiSearchJob,
  getAiSearchJob,
  listAdminAiSearchJobs,
  listAdminUsers,
  listAiSearchJobs,
} from '@/lib/api/dashboard'

type Variant = 'staff' | 'admin'

export function AiSearchPage({ variant }: { variant: Variant }) {
  const qc = useQueryClient()
  const isAdmin = variant === 'admin'
  const [selectedId, setSelectedId] = useState<number | null>(null)
  const [seedTopic, setSeedTopic] = useState('')
  const [industry, setIndustry] = useState('')
  const [region, setRegion] = useState('')
  /** Admin: empty = job owned by you; set to a staff user id to delegate queue ownership. */
  const [delegateOwnerId, setDelegateOwnerId] = useState<number | ''>('')
  const [banner, setBanner] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

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
        if (!Number.isNaN(started) && Date.now() - started > 12 * 60 * 1000) {
          return 15_000
        }
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
    selectedJob && ['generating', 'searching'].includes(selectedJob.status) && jobAgeMs > 4 * 60 * 1000,
  )

  useEffect(() => {
    const st = selectedJob?.status
    if (st === 'done' || st === 'failed') {
      void qc.invalidateQueries({ queryKey: ['ai-search-jobs', variant] })
    }
  }, [selectedJob?.status, variant, qc])

  const createM = useMutation({
    mutationFn: () => {
      if (isAdmin) {
        return createAdminAiSearchJob({
          seed_topic: seedTopic.trim(),
          industry: industry.trim() || undefined,
          region: region.trim() || undefined,
          ...(delegateOwnerId !== '' && Number.isFinite(Number(delegateOwnerId))
            ? { owner_id: Number(delegateOwnerId) }
            : {}),
        })
      }
      return createAiSearchJob({
        seed_topic: seedTopic.trim(),
        industry: industry.trim() || undefined,
        region: region.trim() || undefined,
      })
    },
    onSuccess: (res) => {
      const job = res.data
      if (!res.success || !job) {
        setBanner({ type: 'err', text: res.error ?? 'Could not start job.' })
        return
      }
      setBanner({ type: 'ok', text: `Job #${job.id} queued. Status: ${job.status}.` })
      setSeedTopic('')
      setIndustry('')
      setRegion('')
      void qc.invalidateQueries({ queryKey: ['ai-search-jobs', variant] })
      setSelectedId(job.id)
    },
    onError: (e: unknown) => {
      const ax = e as { response?: { data?: { error?: string } }; message?: string }
      setBanner({
        type: 'err',
        text: ax.response?.data?.error ?? ax.message ?? 'Request failed.',
      })
    },
  })

  const backHref = isAdmin ? '/admin/crawler' : '/crawler'
  const domainsHref = isAdmin ? '/admin/crawler/domains' : '/crawler/domains'

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Button variant="ghost" size="sm" className="-ml-2 mb-1" asChild>
            <Link to={backHref}>← Back</Link>
          </Button>
          <h1 className="flex items-center gap-2 text-2xl font-semibold text-foreground">
            <Sparkles className="h-7 w-7 text-amber-500" aria-hidden />
            AI prospect search
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Uses Gemini to propose buyer-intent search strings (translation, interpretation, tenders, multilingual
            events) and discover domains for your niche. New domains are queued for crawling under your account
            {isAdmin ? ' (optional: delegate queue ownership to a staff user below)' : ''}. Requires{' '}
            <code className="rounded bg-muted px-1">GEMINI_API_KEY</code> on the server. Set{' '}
            <code className="rounded bg-muted px-1">SERPER_API_KEY</code> for stronger SERP-backed discovery.
          </p>
        </div>
        <Button variant="outline" size="sm" onClick={() => void jobsQ.refetch()} disabled={jobsQ.isFetching}>
          <RefreshCw className={`mr-2 h-4 w-4 ${jobsQ.isFetching ? 'animate-spin' : ''}`} />
          Refresh list
        </Button>
      </div>

      {banner && (
        <div
          className={`rounded-lg border px-3 py-2 text-sm ${
            banner.type === 'err' ? 'border-destructive/50 bg-destructive/10 text-destructive' : 'border-border bg-muted/50'
          }`}
        >
          {banner.text}
        </div>
      )}

      <div className="grid gap-6 lg:grid-cols-2">
        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="font-semibold text-foreground">Start a new search</h2>
          <form
            className="mt-3 space-y-3"
            onSubmit={(e) => {
              e.preventDefault()
              setBanner(null)
              if (!seedTopic.trim()) {
                setBanner({ type: 'err', text: 'Enter a seed topic.' })
                return
              }
              createM.mutate()
            }}
          >
            {isAdmin && (
              <div>
                <label className="text-sm font-medium text-foreground">Queue owner (optional)</label>
                <select
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  value={delegateOwnerId === '' ? '' : String(delegateOwnerId)}
                  onChange={(e) => setDelegateOwnerId(e.target.value ? Number(e.target.value) : '')}
                  disabled={usersQ.isLoading}
                >
                  <option value="">You — use my account for discovered domains</option>
                  {staffOptions.map((u) => (
                    <option key={u.id} value={u.id}>
                      Staff: {u.username}
                      {u.email ? ` (${u.email})` : ''}
                    </option>
                  ))}
                </select>
                <p className="mt-1 text-xs text-muted-foreground">
                  Leave on &quot;You&quot; to run the search yourself. Pick a staff user only if you want their queue
                  and ownership.
                </p>
              </div>
            )}
            <div>
              <label className="text-sm font-medium text-foreground">Seed topic</label>
              <input
                className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                placeholder="e.g. international conferences East Africa 2026"
                value={seedTopic}
                onChange={(e) => setSeedTopic(e.target.value)}
              />
            </div>
            <div className="grid gap-3 sm:grid-cols-2">
              <div>
                <label className="text-sm font-medium text-foreground">Industry (optional)</label>
                <input
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  placeholder="NGO, legal, medical…"
                  value={industry}
                  onChange={(e) => setIndustry(e.target.value)}
                />
              </div>
              <div>
                <label className="text-sm font-medium text-foreground">Region (optional)</label>
                <input
                  className="mt-1 w-full rounded-md border border-border bg-background px-3 py-2 text-sm"
                  placeholder="Kenya, East Africa, EAC, Nairobi… (recommended)"
                  value={region}
                  onChange={(e) => setRegion(e.target.value)}
                />
              </div>
            </div>
            <Button type="submit" disabled={createM.isPending}>
              {createM.isPending ? 'Starting…' : 'Run AI search'}
            </Button>
          </form>
        </div>

        <div className="rounded-lg border border-border bg-card p-4">
          <h2 className="font-semibold text-foreground">Recent jobs</h2>
          <div className="mt-2 max-h-80 overflow-auto rounded-md border border-border">
            <table className="min-w-full text-sm">
              <thead className="bg-muted">
                <tr>
                  {isAdmin && <th className="px-2 py-2 text-left">Owner</th>}
                  <th className="px-2 py-2 text-left">Topic</th>
                  <th className="px-2 py-2 text-left">Status</th>
                  <th className="px-2 py-2 text-left">Domains</th>
                  <th className="px-2 py-2 text-left" />
                </tr>
              </thead>
              <tbody>
                {(jobsQ.data?.items ?? []).map((j) => (
                  <tr key={j.id} className="border-t border-border">
                    {isAdmin && (
                      <td className="px-2 py-2 whitespace-nowrap text-muted-foreground">{j.owner_username ?? j.owner_id}</td>
                    )}
                    <td className="px-2 py-2 font-medium">{j.seed_topic}</td>
                    <td className="px-2 py-2">{j.status}</td>
                    <td className="px-2 py-2">{j.domains_discovered}</td>
                    <td className="px-2 py-2">
                      <Button size="sm" variant={selectedId === j.id ? 'default' : 'outline'} onClick={() => setSelectedId(j.id)}>
                        View
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            {jobsQ.isLoading && <p className="p-3 text-sm text-muted-foreground">Loading…</p>}
            {!jobsQ.isLoading && (jobsQ.data?.items?.length ?? 0) === 0 && (
              <p className="p-3 text-sm text-muted-foreground">No jobs yet.</p>
            )}
          </div>
        </div>
      </div>

      {selectedId != null && (
        <div className="rounded-lg border border-border bg-card p-4">
          <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
            <h2 className="font-semibold text-foreground">Job #{selectedId}</h2>
            <Button variant="outline" size="sm" onClick={() => void detailQ.refetch()} disabled={detailQ.isFetching}>
              Refresh detail
            </Button>
          </div>
          {detailQ.isLoading && <p className="text-sm text-muted-foreground">Loading…</p>}
          {detailQ.data?.job && (
            <div className="mb-4 space-y-1 text-sm">
              <p>
                <span className="text-muted-foreground">Status:</span> {detailQ.data.job.status}
              </p>
              {pendingWorkerHint ? (
                <p className="rounded-md border border-amber-500/40 bg-amber-500/10 px-2 py-1.5 text-xs text-amber-950 dark:text-amber-100">
                  Still pending after ~1 minute. The API created the job, but a Celery worker may not be consuming the
                  queue. Start one with:{' '}
                  <code className="rounded bg-background/80 px-1">celery -A leads_app worker -l info</code>
                </p>
              ) : null}
              {longRunningHint ? (
                <p className="rounded-md border border-border bg-muted/50 px-2 py-1.5 text-xs text-muted-foreground">
                  This run is taking several minutes (Gemini and/or many domain checks). The worker will mark the job
                  failed if it exceeds the server time limit (~5 minutes).
                </p>
              ) : null}
              {detailQ.data.job.error_text ? (
                <p className="text-destructive">{detailQ.data.job.error_text}</p>
              ) : null}
              <p>
                <span className="text-muted-foreground">Domains discovered:</span> {detailQ.data.job.domains_discovered}
              </p>
              {Array.isArray(detailQ.data.job.queries_generated) && detailQ.data.job.queries_generated.length > 0 && (
                <details className="mt-2">
                  <summary className="cursor-pointer text-muted-foreground">Generated queries</summary>
                  <ul className="mt-1 list-inside list-disc text-xs">
                    {(detailQ.data.job.queries_generated as { query?: string }[]).map((q, i) => (
                      <li key={i}>{typeof q === 'object' && q?.query ? q.query : JSON.stringify(q)}</li>
                    ))}
                  </ul>
                </details>
              )}
            </div>
          )}
          <div className="overflow-auto rounded-md border border-border">
            <table className="min-w-full text-sm">
              <thead className="bg-muted">
                <tr>
                  <th className="px-2 py-2 text-left">Domain</th>
                  <th className="px-2 py-2 text-left">Source page</th>
                  <th className="px-2 py-2 text-left">Org</th>
                  <th className="px-2 py-2 text-left">Why translation</th>
                  <th className="px-2 py-2 text-left">Actions</th>
                </tr>
              </thead>
              <tbody>
                {(detailQ.data?.results.items ?? []).map((r) => (
                  <tr key={r.id} className="border-t border-border">
                    <td className="px-2 py-2 font-mono text-xs">{r.domain}</td>
                    <td className="max-w-xs px-2 py-2 text-xs">
                      <a
                        href={r.source_url || `https://${r.domain}`}
                        target="_blank"
                        rel="noreferrer"
                        className="line-clamp-2 text-primary hover:underline"
                        title={r.source_url || `https://${r.domain}`}
                      >
                        {r.source_url || `https://${r.domain}`}
                      </a>
                    </td>
                    <td className="px-2 py-2">{r.org_name || r.org_type || '—'}</td>
                    <td className="max-w-xs truncate px-2 py-2 text-muted-foreground">{r.why_needs_translation || '—'}</td>
                    <td className="px-2 py-2">
                      <Button variant="ghost" size="sm" asChild>
                        <a href={r.source_url || `https://${r.domain}`} target="_blank" rel="noreferrer">
                          <ExternalLink className="h-4 w-4" />
                        </a>
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
          <p className="mt-3 text-xs text-muted-foreground">
            Queued domains appear in the{' '}
            <Link className="underline" to={domainsHref}>
              crawler domain queue
            </Link>
            . Crawl them from there or crawler home.
          </p>
        </div>
      )}
    </div>
  )
}
