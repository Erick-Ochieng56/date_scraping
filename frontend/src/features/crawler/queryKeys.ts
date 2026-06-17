/** Centralized TanStack Query keys for the staff crawler domain. */
export const crawlerKeys = {
  all: ['crawler'] as const,
  sources: (limit?: number) => ['crawler', 'sources', limit ?? 'all'] as const,
  domains: (filters: { search?: string; crawl_status?: string; page?: number; pageSize?: number }) =>
    ['crawler', 'domains', filters] as const,
  domainStats: (crawl_status: string) => ['crawler', 'domain-stats', crawl_status] as const,
  runs: (filters: { status?: string; trigger?: string; page?: number; pageSize?: number }) =>
    ['crawler', 'runs', filters] as const,
  runStats: (status: string) => ['crawler', 'run-stats', status] as const,
  run: (runId: number) => ['crawler', 'run', runId] as const,
  runDomains: (runId: number, filters: { state?: string; errors_only?: boolean; page?: number }) =>
    ['crawler', 'run', runId, 'domains', filters] as const,
}

export function invalidateCrawlerQueries(qc: { invalidateQueries: (opts: { queryKey: readonly string[] }) => void }) {
  void qc.invalidateQueries({ queryKey: ['crawler'] })
}
