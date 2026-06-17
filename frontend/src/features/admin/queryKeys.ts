/** Centralized TanStack Query keys for the admin portal. */
export const adminKeys = {
  all: ['admin'] as const,
  metrics: ['admin', 'metrics'] as const,
  settings: ['admin', 'settings'] as const,
  users: (search?: string) => ['admin', 'users', search ?? ''] as const,
  activity: (filters: { page?: number; action?: string; objectType?: string; search?: string }) =>
    ['admin', 'activity', filters] as const,
  pipeline: {
    metrics: ['admin', 'pipeline', 'metrics'] as const,
    prospects: (filters: { status?: string; search?: string; page?: number }) =>
      ['admin', 'pipeline', 'prospects', filters] as const,
    leads: (filters: { status?: string; search?: string; page?: number }) =>
      ['admin', 'pipeline', 'leads', filters] as const,
  },
  scraper: {
    targets: (filters?: { search?: string; page?: number }) => ['admin', 'scraper', 'targets', filters ?? {}] as const,
    runs: (filters?: { status?: string; page?: number }) => ['admin', 'scraper', 'runs', filters ?? {}] as const,
    failedCount: ['admin', 'scraper', 'runs', 'failed-count'] as const,
    runningCount: ['admin', 'scraper', 'runs', 'running-count'] as const,
  },
  crawler: {
    sources: ['admin', 'crawler', 'sources'] as const,
    domains: (filters?: { crawl_status?: string; page?: number }) =>
      ['admin', 'crawler', 'domains', filters ?? {}] as const,
    runs: (filters?: { status?: string; page?: number }) => ['admin', 'crawler', 'runs', filters ?? {}] as const,
    pendingCount: ['admin', 'crawler', 'domains', 'pending-count'] as const,
    runningCount: ['admin', 'crawler', 'runs', 'running-count'] as const,
    failedCount: ['admin', 'crawler', 'runs', 'failed-count'] as const,
  },
}

export function invalidateAdminQueries(qc: { invalidateQueries: (opts: { queryKey: readonly string[] }) => void }) {
  void qc.invalidateQueries({ queryKey: ['admin'] })
}

export function invalidateAdminScraper(qc: { invalidateQueries: (opts: { queryKey: readonly string[] }) => void }) {
  void qc.invalidateQueries({ queryKey: ['admin', 'scraper'] })
}

export function invalidateAdminCrawler(qc: { invalidateQueries: (opts: { queryKey: readonly string[] }) => void }) {
  void qc.invalidateQueries({ queryKey: ['admin', 'crawler'] })
}
