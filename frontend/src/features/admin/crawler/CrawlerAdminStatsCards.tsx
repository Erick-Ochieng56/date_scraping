import { useQuery } from '@tanstack/react-query'

import { adminKeys } from '@/features/admin/queryKeys'
import { listAdminCrawlerDomains, listAdminCrawlerRuns, listAdminCrawlerSources } from '@/shared/api/admin'

export function CrawlerAdminStatsCards() {
  const sourcesQ = useQuery({
    queryKey: adminKeys.crawler.sources,
    queryFn: () => listAdminCrawlerSources({ page_size: 1 }),
  })
  const runsRunningQ = useQuery({
    queryKey: adminKeys.crawler.runningCount,
    queryFn: () => listAdminCrawlerRuns({ page_size: 1, status: 'running' }),
  })
  const domainsPendingQ = useQuery({
    queryKey: adminKeys.crawler.pendingCount,
    queryFn: () => listAdminCrawlerDomains({ page_size: 1, crawl_status: 'pending' }),
  })

  return (
    <div className="grid gap-3 sm:grid-cols-3">
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">Sources</p>
        <p className="text-2xl font-semibold" title={sourcesQ.isError ? 'Failed to load' : undefined}>
          {sourcesQ.isError ? '—' : (sourcesQ.data?.total ?? 0)}
        </p>
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">Running runs</p>
        <p className="text-2xl font-semibold" title={runsRunningQ.isError ? 'Failed to load' : undefined}>
          {runsRunningQ.isError ? '—' : (runsRunningQ.data?.total ?? 0)}
        </p>
      </div>
      <div className="rounded-lg border border-border bg-card p-4">
        <p className="text-sm text-muted-foreground">Pending domains</p>
        <p className="text-2xl font-semibold" title={domainsPendingQ.isError ? 'Failed to load' : undefined}>
          {domainsPendingQ.isError ? '—' : (domainsPendingQ.data?.total ?? 0)}
        </p>
      </div>
    </div>
  )
}
