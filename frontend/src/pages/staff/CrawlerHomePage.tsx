import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { AlertTriangle, Globe, ListTree, Radio, Search, Sparkles } from 'lucide-react'

import { Button } from '@/components/ui/button'
import {
  cancelAllRunningCrawls,
  cancelCrawlRun,
  listCrawlDomains,
  listCrawlRuns,
  listCrawlSources,
  triggerCrawlDomain,
  triggerCrawler,
} from '@/lib/api/dashboard'

function triggerLabel(t: string) {
  if (t === 'scheduled') return 'Scheduled'
  if (t === 'manual') return 'Manual'
  return t
}

export function CrawlerHomePage() {
  const qc = useQueryClient()
  const [banner, setBanner] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)

  const sourcesQ = useQuery({
    queryKey: ['crawl-sources-home'],
    queryFn: () => listCrawlSources({ page_size: 8 }),
  })
  const runsQ = useQuery({
    queryKey: ['crawl-runs-home'],
    queryFn: () => listCrawlRuns({ page_size: 10 }),
    refetchInterval: 5000,
  })
  const domainsQ = useQuery({
    queryKey: ['crawl-domains-home'],
    queryFn: () => listCrawlDomains({ page_size: 8 }),
    refetchInterval: 15000,
  })

  const pendingCountQ = useQuery({
    queryKey: ['crawl-domain-count', 'pending'],
    queryFn: () => listCrawlDomains({ page_size: 1, crawl_status: 'pending' }),
    staleTime: 10_000,
    refetchInterval: 20_000,
  })
  const failedDomainCountQ = useQuery({
    queryKey: ['crawl-domain-count', 'failed'],
    queryFn: () => listCrawlDomains({ page_size: 1, crawl_status: 'failed' }),
    staleTime: 10_000,
    refetchInterval: 20_000,
  })
  const crawlingCountQ = useQuery({
    queryKey: ['crawl-domain-count', 'crawling'],
    queryFn: () => listCrawlDomains({ page_size: 1, crawl_status: 'crawling' }),
    staleTime: 10_000,
    refetchInterval: 15_000,
  })
  const failedRunCountQ = useQuery({
    queryKey: ['crawl-run-count', 'failed'],
    queryFn: () => listCrawlRuns({ page_size: 1, status: 'failed' }),
    staleTime: 10_000,
    refetchInterval: 25_000,
  })

  const invalidateAll = () => {
    void qc.invalidateQueries({ queryKey: ['crawl-sources-home'] })
    void qc.invalidateQueries({ queryKey: ['crawl-domains-home'] })
    void qc.invalidateQueries({ queryKey: ['crawl-runs-home'] })
    void qc.invalidateQueries({ queryKey: ['crawl-domain-count'] })
    void qc.invalidateQueries({ queryKey: ['crawl-run-count'] })
    void qc.invalidateQueries({ queryKey: ['crawler-runs-page'] })
    void qc.invalidateQueries({ queryKey: ['crawl-domains'] })
  }

  const triggerM = useMutation({
    mutationFn: triggerCrawler,
    onMutate: () => setBanner(null),
    onSuccess: (data) => {
      setBanner({ type: 'ok', text: data.message ?? 'Discovery queued.' })
      invalidateAll()
    },
    onError: (err: unknown) => {
      const ax = err as { response?: { data?: { error?: string } } }
      setBanner({ type: 'err', text: ax.response?.data?.error ?? 'Could not queue discovery.' })
    },
  })

  const cancelAllM = useMutation({
    mutationFn: cancelAllRunningCrawls,
    onMutate: () => setBanner(null),
    onSuccess: (data) => {
      setBanner({ type: 'ok', text: `Cancelled ${data.cancelled ?? 0} run(s).` })
      invalidateAll()
    },
    onError: (err: unknown) => {
      const ax = err as { response?: { data?: { error?: string } } }
      setBanner({ type: 'err', text: ax.response?.data?.error ?? 'Batch cancel failed.' })
    },
  })

  const cancelOneM = useMutation({
    mutationFn: (runId: number) => cancelCrawlRun(runId),
    onMutate: () => setBanner(null),
    onSuccess: () => {
      setBanner({ type: 'ok', text: 'Run cancelled.' })
      invalidateAll()
    },
    onError: (err: unknown) => {
      const ax = err as { response?: { data?: { error?: string } } }
      setBanner({ type: 'err', text: ax.response?.data?.error ?? 'Could not cancel run.' })
    },
  })

  const crawlDomainM = useMutation({
    mutationFn: (domainId: number) => triggerCrawlDomain(domainId),
    onMutate: () => setBanner(null),
    onSuccess: (data) => {
      setBanner({ type: 'ok', text: `Crawl started (run #${data.run_id}).` })
      invalidateAll()
    },
    onError: (err: unknown) => {
      const ax = err as { response?: { data?: { error?: string } } }
      setBanner({ type: 'err', text: ax.response?.data?.error ?? 'Could not start crawl.' })
    },
  })

  const runs = runsQ.data?.items ?? []
  const runningRuns = runs.filter((r) => r.status === 'running').length
  const failedInSample = runs.filter((r) => r.status === 'failed').length

  const pendingTotal = pendingCountQ.data?.total ?? 0
  const failedDomainsTotal = failedDomainCountQ.data?.total ?? 0
  const crawlingTotal = crawlingCountQ.data?.total ?? 0
  const failedRunsTotal = failedRunCountQ.data?.total ?? 0

  const attentionItems: Array<{ label: string; to: string }> = []
  if (failedRunsTotal > 0) {
    attentionItems.push({ label: `${failedRunsTotal} failed crawl run(s)`, to: '/crawler/runs?status=failed' })
  }
  if (failedDomainsTotal > 0) {
    attentionItems.push({ label: `${failedDomainsTotal} failed domain(s) in queue`, to: '/crawler/domains?crawl_status=failed' })
  }
  if (crawlingTotal > 5) {
    attentionItems.push({ label: `${crawlingTotal} domains crawling`, to: '/crawler/domains?crawl_status=crawling' })
  }

  const sources = sourcesQ.data?.items ?? []
  const domainRows = domainsQ.data?.items ?? []

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-foreground">Crawler home</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Discovery sources feed the domain queue; runs track batch progress. Separate from scraper targets — nothing here
            touches scrape targets or scrape runs.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => invalidateAll()}>
            Refresh all
          </Button>
          <Button
            variant="outline"
            disabled={cancelAllM.isPending}
            onClick={() => {
              const ok = window.confirm('Cancel all currently running crawl runs for your account?')
              if (ok) cancelAllM.mutate()
            }}
          >
            {cancelAllM.isPending ? 'Cancelling...' : 'Cancel all running'}
          </Button>
          <Button disabled={triggerM.isPending} onClick={() => triggerM.mutate()}>
            {triggerM.isPending ? 'Queueing...' : 'Run scheduled discovery'}
          </Button>
        </div>
      </div>

      {banner ? (
        <div
          className={`rounded-lg border px-3 py-2 text-sm ${
            banner.type === 'err'
              ? 'border-destructive/40 bg-destructive/10 text-destructive'
              : 'border-border bg-muted/50 text-foreground'
          }`}
        >
          {banner.text}
        </div>
      ) : null}

      {attentionItems.length > 0 ? (
        <div className="rounded-xl border border-amber-300/60 bg-amber-50/70 p-4 dark:border-amber-700/50 dark:bg-amber-950/20">
          <div className="flex items-center gap-2 text-amber-900 dark:text-amber-300">
            <AlertTriangle className="size-4 shrink-0" aria-hidden />
            <h3 className="font-semibold">Crawler attention</h3>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {attentionItems.map((item) => (
              <Button key={item.label} size="sm" variant="outline" asChild>
                <Link to={item.to}>{item.label}</Link>
              </Button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="flex items-center gap-2 font-semibold text-foreground">
          <ListTree className="size-4 text-primary" aria-hidden />
          Crawler workflow
        </h3>
        <ol className="mt-3 grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <li className="rounded-md border border-border bg-muted/30 p-3">
            <span className="font-medium text-foreground">1. Ad-hoc search</span>
            <p className="mt-1 text-muted-foreground">Preview URLs from a phrase and queue them for crawling.</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button size="sm" variant="outline" asChild>
                <Link to="/crawler/discover">
                  <Search className="mr-1 inline size-3.5" aria-hidden />
                  Open discover
                </Link>
              </Button>
              <Button size="sm" variant="outline" asChild>
                <Link to="/crawler/ai-search">
                  <Sparkles className="mr-1 inline size-3.5" aria-hidden />
                  AI search
                </Link>
              </Button>
            </div>
          </li>
          <li className="rounded-md border border-border bg-muted/30 p-3">
            <span className="font-medium text-foreground">2. Sources</span>
            <p className="mt-1 text-muted-foreground">Enabled sources drive scheduled discovery runs.</p>
            <p className="mt-2 text-xs text-muted-foreground">{sourcesQ.data?.total ?? 0} source(s) total</p>
          </li>
          <li className="rounded-md border border-border bg-muted/30 p-3">
            <span className="font-medium text-foreground">3. Domain queue</span>
            <p className="mt-1 text-muted-foreground">Pending: {pendingTotal} · Crawling: {crawlingTotal}</p>
            <Button className="mt-2" size="sm" variant="outline" asChild>
              <Link to="/crawler/domains">
                <Globe className="mr-1 inline size-3.5" aria-hidden />
                Open queue
              </Link>
            </Button>
          </li>
          <li className="rounded-md border border-border bg-muted/30 p-3">
            <span className="font-medium text-foreground">4. Runs & results</span>
            <p className="mt-1 text-muted-foreground">Running now: {runningRuns} · Failed (all time in API): {failedRunsTotal}</p>
            <Button className="mt-2" size="sm" variant="outline" asChild>
              <Link to="/crawler/runs">
                <Radio className="mr-1 inline size-3.5" aria-hidden />
                Crawl runs
              </Link>
            </Button>
          </li>
        </ol>
      </div>

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Sources</p>
          <p className="text-xl font-semibold">{sourcesQ.data?.total ?? 0}</p>
          <p className="mt-1 text-xs text-muted-foreground">Enabled sources run on “scheduled discovery”.</p>
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Pending domains</p>
          <p className="text-xl font-semibold">{pendingTotal}</p>
          <Link className="text-sm text-primary hover:underline" to="/crawler/domains?crawl_status=pending">
            Review queue
          </Link>
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Crawling now</p>
          <p className="text-xl font-semibold">{crawlingTotal}</p>
          <Link className="text-sm text-primary hover:underline" to="/crawler/domains?crawl_status=crawling">
            Watch active
          </Link>
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Running runs (sample)</p>
          <p className="text-xl font-semibold">{runningRuns}</p>
          <Link className="text-sm text-primary hover:underline" to="/crawler/runs?status=running">
            Full list
          </Link>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="rounded-lg border border-border p-4">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-semibold text-foreground">Your sources (snapshot)</h3>
            <Button size="sm" variant="ghost" className="h-8 px-2 text-xs" asChild>
              <Link to="/crawler/discover">Discover UI</Link>
            </Button>
          </div>
          <div className="mt-3 overflow-auto rounded-md border border-border">
            <table className="min-w-full text-sm">
              <thead className="bg-muted">
                <tr>
                  <th className="px-3 py-2 text-left">Name</th>
                  <th className="px-3 py-2 text-left">Type</th>
                  <th className="px-3 py-2 text-left">On</th>
                </tr>
              </thead>
              <tbody>
                {sources.length === 0 && !sourcesQ.isLoading ? (
                  <tr>
                    <td colSpan={3} className="px-3 py-4 text-muted-foreground">
                      No sources yet — use Discover or ask an admin to add crawl sources.
                    </td>
                  </tr>
                ) : null}
                {sources.map((s) => (
                  <tr key={s.id} className="border-t border-border">
                    <td className="px-3 py-2 font-medium">{s.name}</td>
                    <td className="px-3 py-2">{s.source_type}</td>
                    <td className="px-3 py-2">{s.enabled ? 'Yes' : 'No'}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>

        <div className="rounded-lg border border-border p-4">
          <div className="flex items-center justify-between gap-2">
            <h3 className="font-semibold text-foreground">Queue quick actions</h3>
            <Button size="sm" variant="ghost" className="h-8 px-2 text-xs" asChild>
              <Link to="/crawler/domains">All domains</Link>
            </Button>
          </div>
          <p className="mt-1 text-xs text-muted-foreground">Crawl a domain immediately (creates a manual crawl run).</p>
          <div className="mt-3 overflow-auto rounded-md border border-border">
            <table className="min-w-full text-sm">
              <thead className="bg-muted">
                <tr>
                  <th className="px-3 py-2 text-left">Domain</th>
                  <th className="px-3 py-2 text-left">Status</th>
                  <th className="px-3 py-2 text-left">Action</th>
                </tr>
              </thead>
              <tbody>
                {domainRows.length === 0 && !domainsQ.isLoading ? (
                  <tr>
                    <td colSpan={3} className="px-3 py-4 text-muted-foreground">
                      No domains in the recent snapshot — run discovery or open the full queue.
                    </td>
                  </tr>
                ) : null}
                {domainRows.map((d) => (
                  <tr key={d.id} className="border-t border-border align-middle">
                    <td className="max-w-[200px] px-3 py-2">
                      <span className="break-all font-mono text-xs">{d.domain}</span>
                    </td>
                    <td className="px-3 py-2">{d.crawl_status}</td>
                    <td className="px-3 py-2">
                      <Button
                        size="sm"
                        variant="outline"
                        disabled={crawlDomainM.isPending}
                        onClick={() => {
                          const ok = window.confirm(`Start a manual crawl for ${d.domain}?`)
                          if (ok) crawlDomainM.mutate(d.id)
                        }}
                      >
                        Crawl now
                      </Button>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </div>

      <div className="rounded-lg border border-border p-4">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="font-semibold text-foreground">Recent crawl runs</h3>
          <span className="text-xs text-muted-foreground">
            Failed in this list: {failedInSample} · See{' '}
            <Link className="text-primary hover:underline" to="/crawler/runs">
              all runs
            </Link>
          </span>
        </div>
        <div className="mt-3 overflow-auto rounded-md border border-border">
          <table className="min-w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="px-3 py-2 text-left">Run</th>
                <th className="px-3 py-2 text-left">Status</th>
                <th className="px-3 py-2 text-left">Trigger</th>
                <th className="px-3 py-2 text-left">Domains</th>
                <th className="px-3 py-2 text-left">Prospects</th>
                <th className="px-3 py-2 text-left">Started</th>
                <th className="px-3 py-2 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {runs.length === 0 && !runsQ.isLoading ? (
                <tr>
                  <td colSpan={7} className="px-3 py-4 text-muted-foreground">
                    No runs yet — trigger scheduled discovery or crawl a domain from the queue.
                  </td>
                </tr>
              ) : null}
              {runs.map((r) => (
                <tr key={r.id} className="border-t border-border">
                  <td className="px-3 py-2 font-medium">#{r.id}</td>
                  <td className="px-3 py-2">{r.status_display || r.status}</td>
                  <td className="px-3 py-2">{triggerLabel(r.trigger)}</td>
                  <td className="px-3 py-2">{r.domains_queued}</td>
                  <td className="px-3 py-2">
                    +{r.prospects_created} / {r.prospects_updated}
                  </td>
                  <td className="px-3 py-2 whitespace-nowrap">{new Date(r.started_at).toLocaleString()}</td>
                  <td className="px-3 py-2">
                    <div className="flex flex-wrap gap-2">
                      <Button size="sm" variant="outline" asChild>
                        <Link to={`/crawler/runs/${r.id}`}>Details</Link>
                      </Button>
                      {r.status === 'running' ? (
                        <Button
                          size="sm"
                          variant="outline"
                          disabled={cancelOneM.isPending}
                          onClick={() => {
                            const ok = window.confirm(`Cancel crawl run #${r.id}?`)
                            if (ok) cancelOneM.mutate(r.id)
                          }}
                        >
                          Cancel
                        </Button>
                      ) : null}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
