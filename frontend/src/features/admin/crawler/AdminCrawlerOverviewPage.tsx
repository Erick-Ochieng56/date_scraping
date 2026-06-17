import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { CrawlerAdminStatsCards } from '@/features/admin/crawler/CrawlerAdminStatsCards'
import { PageHeader } from '@/shared/components/PageHeader'

export function AdminCrawlerOverviewPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Crawler"
        description="Global crawl sources, domain queue, and run orchestration. Use buyer-intent AI search queries for best discovery results."
      />

      <CrawlerAdminStatsCards />

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="font-semibold text-foreground">Quick links</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" variant="outline" asChild>
            <Link to="/admin/crawler/sources">All sources</Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/admin/crawler/domains">Domain queue</Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/admin/crawler/runs">All runs</Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/admin/ai-search">AI search (Gemini)</Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/crawler/discover">Staff discover UI</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
