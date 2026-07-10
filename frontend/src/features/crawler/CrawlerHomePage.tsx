import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Globe, ListTree, Radio, Search } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { AttentionPanel, type AttentionItem } from '@/features/home/AttentionPanel'
import { CrawlSessionPanel } from '@/features/crawler/CrawlSessionPanel'
import { Button } from '@/components/ui/button'
import { crawlerKeys, invalidateCrawlerQueries } from '@/features/crawler/queryKeys'
import { getApiErrorMessage } from '@/shared/api/errors'
import { cancelAllRunningCrawls, listCrawlDomains, listCrawlRuns, listCrawlSources } from '@/shared/api/crawler'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { KpiCard } from '@/shared/components/KpiCard'
import { PageHeader } from '@/shared/components/PageHeader'
import { SectionEyebrow } from '@/shared/components/SectionEyebrow'
import { TextLink } from '@/shared/components/TextLink'

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
  const sourcesTotal = sourcesQ.data?.total ?? 0

  const attentionItems: AttentionItem[] = []
  if (failedRunsTotal > 0) {
    attentionItems.push({
      label: `${failedRunsTotal} failed crawl run${failedRunsTotal === 1 ? '' : 's'}`,
      to: '/crawler/runs?status=failed',
      action: 'View failed runs →',
    })
  }
  if (failedDomainsTotal > 0) {
    attentionItems.push({
      label: `${failedDomainsTotal} failed domain${failedDomainsTotal === 1 ? '' : 's'} in queue`,
      to: '/crawler/domains?crawl_status=failed',
      action: 'View domain queue →',
    })
  }
  if (crawlingTotal > 5) {
    attentionItems.push({
      label: `${crawlingTotal} domains crawling`,
      to: '/crawler/domains?crawl_status=crawling',
      action: 'Watch active domains →',
    })
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Crawler overview"
        description="Discovery sources feed the domain queue; runs track batch progress."
        actions={
          <>
            <Button variant="outline" onClick={() => invalidateCrawlerQueries(qc)}>
              Refresh
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
          </>
        }
      />

      <AlertBanner message={banner.message} error={banner.error} />

      <CrawlSessionPanel onBanner={setBanner} />
      <p className="text-right text-sm">
        <TextLink to="/crawler/schedules">Manage recurring schedules →</TextLink>
      </p>

      <section className="space-y-3">
        <SectionEyebrow>Queue status</SectionEyebrow>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard label="Sources" value={sourcesTotal} />
          <KpiCard
            label="Pending domains"
            value={pendingTotal}
            action={pendingTotal > 0 ? 'View pending domains' : undefined}
            to={pendingTotal > 0 ? '/crawler/domains?crawl_status=pending' : undefined}
          />
          <KpiCard
            label="Crawling now"
            value={crawlingTotal}
            action={crawlingTotal > 0 ? 'Watch active domains' : undefined}
            to={crawlingTotal > 0 ? '/crawler/domains?crawl_status=crawling' : undefined}
          />
          <KpiCard
            label="Running runs"
            value={runningRuns}
            action={runningRuns > 0 ? 'View running crawl runs' : undefined}
            to={runningRuns > 0 ? '/crawler/runs?status=running' : undefined}
          />
        </div>
      </section>

      <AttentionPanel items={attentionItems} />

      <section className="space-y-3">
        <SectionEyebrow>Crawler workflow</SectionEyebrow>
        <ol className="grid gap-3 text-sm sm:grid-cols-2 lg:grid-cols-4">
          <li className="rounded-lg border border-border bg-card p-3">
            <div className="flex items-center gap-2 font-medium text-foreground">
              <Search className="size-4 text-secondary" aria-hidden />
              1. Ad-hoc search
            </div>
            <p className="mt-1 text-muted-foreground">Preview URLs from a phrase and queue them for crawling.</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button size="sm" variant="outline" asChild>
                <Link to="/crawler/discover">Open discover</Link>
              </Button>
              <Button size="sm" variant="outline" asChild>
                <Link to="/crawler/ai-search">AI search</Link>
              </Button>
            </div>
          </li>
          <li className="rounded-lg border border-border bg-card p-3">
            <div className="flex items-center gap-2 font-medium text-foreground">
              <ListTree className="size-4 text-secondary" aria-hidden />
              2. Sources
            </div>
            <p className="mt-1 text-muted-foreground">Enabled sources drive scheduled discovery runs.</p>
            <p className="mt-2 text-xs text-tertiary">{sourcesTotal} source(s) configured</p>
          </li>
          <li className="rounded-lg border border-border bg-card p-3">
            <div className="flex items-center gap-2 font-medium text-foreground">
              <Globe className="size-4 text-secondary" aria-hidden />
              3. Domain queue
            </div>
            <p className="mt-1 text-muted-foreground">
              Pending: {pendingTotal} · Crawling: {crawlingTotal}
            </p>
            <Button className="mt-2" size="sm" variant="outline" asChild>
              <Link to="/crawler/domains">Open domain queue</Link>
            </Button>
          </li>
          <li className="rounded-lg border border-border bg-card p-3">
            <div className="flex items-center gap-2 font-medium text-foreground">
              <Radio className="size-4 text-secondary" aria-hidden />
              4. Runs & results
            </div>
            <p className="mt-1 text-muted-foreground">
              Running: {runningRuns} · Failed (7d): {failedRunsTotal}
            </p>
            <Button className="mt-2" size="sm" variant="outline" asChild>
              <Link to="/crawler/runs">View crawl runs</Link>
            </Button>
          </li>
        </ol>
      </section>
    </div>
  )
}
