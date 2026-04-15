import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { fetchMetricsSummary, listCrawlRuns, listScrapeRuns } from '@/lib/api/dashboard'

export function AdminHomePage() {
  const metricsQ = useQuery({
    queryKey: ['admin-overview-metrics'],
    queryFn: fetchMetricsSummary,
    refetchInterval: 15000,
  })
  const scrapeFailedQ = useQuery({
    queryKey: ['admin-overview-scrape-failed'],
    queryFn: () => listScrapeRuns({ page_size: 1, status: 'failed' }),
    refetchInterval: 15000,
  })
  const crawlFailedQ = useQuery({
    queryKey: ['admin-overview-crawl-failed'],
    queryFn: () => listCrawlRuns({ page_size: 1, status: 'failed' }),
    refetchInterval: 15000,
  })

  const m = metricsQ.data

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-foreground">Admin overview</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Global operational visibility and controls across scraper, crawler, and pipeline workflows.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" asChild>
            <Link to="/admin/monitoring">Open monitoring</Link>
          </Button>
          <Button variant="outline" asChild>
            <Link to="/admin/audit">Open audit log</Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Enabled targets</p>
          <p className="text-2xl font-semibold">{m?.targets_enabled ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Scrape runs (7d)</p>
          <p className="text-2xl font-semibold">{m?.scrape_runs_recent ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Crawl runs (7d)</p>
          <p className="text-2xl font-semibold">{m?.crawl_runs_recent ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Prospects (new)</p>
          <p className="text-2xl font-semibold">{m?.prospects_new ?? 0}</p>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="font-semibold text-foreground">Attention and operations</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" variant="outline" asChild>
            <Link to="/admin/scraper/runs">Failed scrape runs: {scrapeFailedQ.data?.total ?? 0}</Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/admin/crawler/runs">Failed crawl runs: {crawlFailedQ.data?.total ?? 0}</Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/admin/pipeline">Interested leads: {m?.leads_interested ?? 0}</Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/admin/ai-search">AI prospect search</Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/admin/crawler/sources">Crawl sources</Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/admin/crawler/domains">Domain queue</Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/admin/scraper/targets">Scrape targets</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
