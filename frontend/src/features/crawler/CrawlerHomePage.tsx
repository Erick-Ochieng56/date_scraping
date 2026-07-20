import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, Globe, ListTree, Radio, Search, Sparkles } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { crawlerKeys, invalidateCrawlerQueries } from '@/features/crawler/queryKeys'
import { getApiErrorMessage } from '@/shared/api/errors'
import { cancelAllRunningCrawls, listCrawlDomains, listCrawlRuns, listCrawlSources, triggerCrawler } from '@/shared/api/crawler'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { PageHeader } from '@/shared/components/PageHeader'

export function CrawlerHomePage() {
  const qc = useQueryClient()
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  const sourcesQ = useQuery({
    queryKey: crawlerKeys.sources(8),
    queryFn: () => listCrawlSources({ page_size: 8 }),
  })

  const runsQ = useQuery({
    queryKey: crawlerKeys.runs({ pageSize: 10 }),
    queryFn: () => listCrawlRuns({ page_size: 10 }),
    refetchInterval: 5000,
  })

  const pendingCountQ = useQuery({
    queryKey: crawlerKeys.domainStats('pending'),
    queryFn: () => listCrawlDomains({ page_size: 1, crawl_status: 'pending' }),
    staleTime: 10_000,
    refetchInterval: 20_000,
  })

  const failedDomainCountQ = useQuery({
    queryKey: crawlerKeys.domainStats('failed'),
    queryFn: () => listCrawlDomains({ page_size: 1, crawl_status: 'failed' }),
    staleTime: 10_000,
    refetchInterval: 20_000,
  })

  const crawlingCountQ = useQuery({
    queryKey: crawlerKeys.domainStats('crawling'),
    queryFn: () => listCrawlDomains({ page_size: 1, crawl_status: 'crawling' }),
    staleTime: 10_000,
    refetchInterval: 15_000,
  })

  const failedRunCountQ = useQuery({
    queryKey: crawlerKeys.runStats('failed'),
    queryFn: () => listCrawlRuns({ page_size: 1, status: 'failed' }),
    staleTime: 10_000,
    refetchInterval: 25_000,
  })

  const triggerM = useMutation({
    mutationFn: triggerCrawler,
    onSuccess: (data) => {
      setBanner({ message: data.message ?? 'Discovery queued.' })
      invalidateCrawlerQueries(qc)
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const cancelAllM = useMutation({
    mutationFn: cancelAllRunningCrawls,
    onSuccess: (data) => {
      setBanner({ message: `Cancelled ${data.cancelled ?? 0} run(s).` })
      invalidateCrawlerQueries(qc)
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const runs = runsQ.data?.items ?? []
  const runningRuns = runs.filter((r) => r.status === 'running').length

  const pendingTotal = pendingCountQ.data?.total ?? 0
  const failedDomainsTotal = failedDomainCountQ.data?.total ?? 0
  const crawlingTotal = crawlingCountQ.data?.total ?? 0
  const failedRunsTotal = failedRunCountQ.data?.total ?? 0

  const attentionItems: Array<{ label: string; to: string }> = []
  if (failedRunsTotal > 0) {
    attentionItems.push({ label: `${failedRunsTotal} failed crawl run(s)`, to: '/crawler/runs?status=failed' })
  }
  if (failedDomainsTotal > 0) {
    attentionItems.push({
      label: `${failedDomainsTotal} failed domain(s) in queue`,
      to: '/crawler/domains?crawl_status=failed',
    })
  }
  if (crawlingTotal > 5) {
    attentionItems.push({ label: `${crawlingTotal} domains crawling`, to: '/crawler/domains?crawl_status=crawling' })
  }

  return (
    <div className="space-y-5">
      <PageHeader
        title="Crawler overview"
        description="Discovery sources feed the domain queue; runs track batch progress. Separate from scraper targets and scrape runs."
        actions={
          <>
            <Button variant="outline" onClick={() => invalidateCrawlerQueries(qc)}>
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
              {cancelAllM.isPending ? 'Cancelling…' : 'Cancel all running'}
            </Button>
            <Button disabled={triggerM.isPending} onClick={() => triggerM.mutate()}>
              {triggerM.isPending ? 'Queueing…' : 'Run scheduled discovery'}
            </Button>
          </>
        }
      />

      <AlertBanner message={banner.message} error={banner.error} />

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
            <p className="mt-2 text-xs text-muted-foreground">
              {sourcesQ.isError ? <span title="Failed to load">—</span> : (sourcesQ.data?.total ?? 0)} source(s) total
            </p>
          </li>
          <li className="rounded-md border border-border bg-muted/30 p-3">
            <span className="font-medium text-foreground">3. Domain queue</span>
            <p className="mt-1 text-muted-foreground">
              Pending: {pendingCountQ.isError ? <span title="Failed to load">—</span> : pendingTotal} · Crawling:{' '}
              {crawlingCountQ.isError ? <span title="Failed to load">—</span> : crawlingTotal}
            </p>
            <Button className="mt-2" size="sm" variant="outline" asChild>
              <Link to="/crawler/domains">
                <Globe className="mr-1 inline size-3.5" aria-hidden />
                Open queue
              </Link>
            </Button>
          </li>
          <li className="rounded-md border border-border bg-muted/30 p-3">
            <span className="font-medium text-foreground">4. Runs & results</span>
            <p className="mt-1 text-muted-foreground">
              Running now: {runsQ.isError ? <span title="Failed to load">—</span> : runningRuns} · Failed (all time):{' '}
              {failedRunCountQ.isError ? <span title="Failed to load">—</span> : failedRunsTotal}
            </p>
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
          <p className="text-xl font-semibold" title={sourcesQ.isError ? 'Failed to load' : undefined}>
            {sourcesQ.isError ? '—' : (sourcesQ.data?.total ?? 0)}
          </p>
          <p className="mt-1 text-xs text-muted-foreground">Enabled sources run on scheduled discovery.</p>
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Pending domains</p>
          <p className="text-xl font-semibold" title={pendingCountQ.isError ? 'Failed to load' : undefined}>
            {pendingCountQ.isError ? '—' : pendingTotal}
          </p>
          <Link className="text-sm text-primary hover:underline" to="/crawler/domains?crawl_status=pending">
            Review queue
          </Link>
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Crawling now</p>
          <p className="text-xl font-semibold" title={crawlingCountQ.isError ? 'Failed to load' : undefined}>
            {crawlingCountQ.isError ? '—' : crawlingTotal}
          </p>
          <Link className="text-sm text-primary hover:underline" to="/crawler/domains?crawl_status=crawling">
            Watch active
          </Link>
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Running runs</p>
          <p className="text-xl font-semibold" title={runsQ.isError ? 'Failed to load' : undefined}>
            {runsQ.isError ? '—' : runningRuns}
          </p>
          <Link className="text-sm text-primary hover:underline" to="/crawler/runs?status=running">
            Full list
          </Link>
        </div>
      </div>
    </div>
  )
}
