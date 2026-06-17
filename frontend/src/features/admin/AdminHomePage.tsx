import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { adminKeys } from '@/features/admin/queryKeys'
import { listCrawlRuns } from '@/shared/api/crawler'
import { listScrapeRuns } from '@/shared/api/scraper'
import { fetchMetricsSummary } from '@/shared/api/metrics'
import { PageHeader } from '@/shared/components/PageHeader'

export function AdminHomePage() {
  const metricsQ = useQuery({
    queryKey: adminKeys.metrics,
    queryFn: fetchMetricsSummary,
    refetchInterval: 15_000,
  })
  const scrapeFailedQ = useQuery({
    queryKey: ['admin', 'overview', 'scrape-failed'],
    queryFn: () => listScrapeRuns({ page_size: 1, status: 'failed' }),
    refetchInterval: 15_000,
  })
  const crawlFailedQ = useQuery({
    queryKey: ['admin', 'overview', 'crawl-failed'],
    queryFn: () => listCrawlRuns({ page_size: 1, status: 'failed' }),
    refetchInterval: 15_000,
  })

  const m = metricsQ.data

  return (
    <div className="space-y-5">
      <PageHeader
        title="Admin overview"
        description="Global operational visibility and controls across scraper, crawler, and pipeline workflows."
        actions={
          <>
            <Button variant="outline" asChild>
              <Link to="/admin/monitoring">Open monitoring</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/admin/audit">Open audit log</Link>
            </Button>
          </>
        }
      />

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
            <Link to="/admin/scraper/runs?status=failed">
              Failed scrape runs: {scrapeFailedQ.data?.total ?? 0}
            </Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/admin/crawler/runs?status=failed">
              Failed crawl runs: {crawlFailedQ.data?.total ?? 0}
            </Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/admin/pipeline?tab=leads&status=interested">
              Interested leads: {m?.leads_interested ?? 0}
            </Link>
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
