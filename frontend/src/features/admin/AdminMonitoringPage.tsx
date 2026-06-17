import { useState } from 'react'
import { Link } from 'react-router-dom'

import { AdminCrawlerRunsTable } from '@/features/admin/crawler/AdminCrawlerRunsTable'
import { AdminScraperRunsTable } from '@/features/admin/scraper/AdminScraperRunsTable'
import { Button } from '@/components/ui/button'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { PageHeader } from '@/shared/components/PageHeader'

export function AdminMonitoringPage() {
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  const onMessage = (m: string | null, e: string | null) => {
    setBanner(e ? { error: e } : m ? { message: m } : {})
  }

  return (
    <div className="space-y-4">
      <PageHeader
        title="Monitoring"
        description="Incident center for failed scrape and crawl runs. Retry failed scrapes or review crawl errors below."
        actions={
          <Button variant="outline" asChild>
            <Link to="/admin">Back to admin home</Link>
          </Button>
        }
      />

      <AlertBanner message={banner.message} error={banner.error} />

      <div className="grid gap-3 sm:grid-cols-2">
        <div className="rounded-lg border border-border bg-card p-4 text-sm">
          <p className="font-medium text-foreground">Scraper incidents</p>
          <p className="mt-1 text-muted-foreground">Failed runs can be retried individually.</p>
          <Button variant="link" className="mt-2 h-auto p-0" asChild>
            <Link to="/admin/scraper/runs?status=failed">Open scraper runs</Link>
          </Button>
        </div>
        <div className="rounded-lg border border-border bg-card p-4 text-sm">
          <p className="font-medium text-foreground">Crawler incidents</p>
          <p className="mt-1 text-muted-foreground">Inspect failed batches; use domain queue to re-crawl.</p>
          <Button variant="link" className="mt-2 h-auto p-0" asChild>
            <Link to="/admin/crawler/domains?crawl_status=failed">Open domain queue</Link>
          </Button>
        </div>
      </div>

      <div>
        <h3 className="mb-2 font-semibold text-foreground">Failed scrape runs</h3>
        <AdminScraperRunsTable onMessage={onMessage} initialStatus="failed" syncUrl={false} />
      </div>

      <div>
        <h3 className="mb-2 font-semibold text-foreground">Failed crawl runs</h3>
        <AdminCrawlerRunsTable onMessage={onMessage} initialStatus="failed" syncUrl={false} />
      </div>
    </div>
  )
}
