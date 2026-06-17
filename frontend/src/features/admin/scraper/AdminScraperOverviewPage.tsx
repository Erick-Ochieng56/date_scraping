import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { ScraperAdminStatsCards } from '@/features/admin/scraper/ScraperAdminStatsCards'
import { PageHeader } from '@/shared/components/PageHeader'

export function AdminScraperOverviewPage() {
  return (
    <div className="space-y-4">
      <PageHeader
        title="Scraper"
        description="Global scraper targets and run history across all users."
      />

      <ScraperAdminStatsCards />

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="font-semibold text-foreground">Quick links</h3>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" variant="outline" asChild>
            <Link to="/admin/scraper/targets">All targets</Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/admin/scraper/runs">All runs</Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/admin/scraper/runs?status=failed">Failed runs</Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/targets">Staff targets UI</Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/runs">Staff runs UI</Link>
          </Button>
        </div>
      </div>
    </div>
  )
}
