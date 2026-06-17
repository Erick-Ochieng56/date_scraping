import { useQuery } from '@tanstack/react-query'

import { adminKeys } from '@/features/admin/queryKeys'
import { listAdminScrapeRuns, listAdminScraperTargets } from '@/shared/api/admin'

export function ScraperAdminStatsCards() {
  const targetsQ = useQuery({
    queryKey: adminKeys.scraper.targets(),
    queryFn: () => listAdminScraperTargets({ page_size: 1 }),
  })
  const failedQ = useQuery({
    queryKey: adminKeys.scraper.failedCount,
    queryFn: () => listAdminScrapeRuns({ page_size: 1, status: 'failed' }),
  })
  const runningQ = useQuery({
    queryKey: adminKeys.scraper.runningCount,
    queryFn: () => listAdminScrapeRuns({ page_size: 1, status: 'running' }),
  })

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">Targets</p>
        <p className="text-2xl font-semibold">{targetsQ.data?.total ?? 0}</p>
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">Failed runs</p>
        <p className="text-2xl font-semibold">{failedQ.data?.total ?? 0}</p>
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">Running runs</p>
        <p className="text-2xl font-semibold">{runningQ.data?.total ?? 0}</p>
      </div>
    </div>
  )
}
