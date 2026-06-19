import { apiClient } from '@/lib/api/client'

import type {
  ActivityLogEntry,
  ActivityLogFilters,
  AdminScrapeRun,
  AdminScraperTarget,
  AdminSettingsStatus,
  AdminUser,
  AISearchJob,
  AISearchJobDetail,
  AISearchResult,
  CrawlRun,
  CrawlSource,
  CrawlDomain,
  Paginated,
} from './types'

export async function listAdminActivity(params?: {
  page?: number
  page_size?: number
  action?: string
  object_type?: string
  user_id?: number
  search?: string
}) {
  const { data } = await apiClient.get<{
    success: boolean
    data: Paginated<ActivityLogEntry>
    filters: ActivityLogFilters
  }>('/dashboard/api/admin/v1/activity/', { params })
  return { items: data.data, filters: data.filters }
}

export async function fetchAdminSettingsStatus() {
  const { data } = await apiClient.get<{ success: boolean; data: AdminSettingsStatus }>(
    '/dashboard/api/admin/v1/settings/status/'
  )
  return data.data
}

export async function listAdminUsers(params?: { page?: number; page_size?: number; search?: string }) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<AdminUser> }>(
    '/dashboard/api/admin/v1/users/',
    { params }
  )
  return data.data
}

export async function createStaffUser(payload: { username: string; password: string; email?: string }) {
  const { data } = await apiClient.post<{ success: boolean; data: AdminUser; error?: string }>(
    '/dashboard/api/admin/v1/users/create-staff/',
    payload
  )
  return data
}

export async function updateAdminUser(
  userId: number,
  payload: {
    role?: 'admin' | 'staff'
    is_active?: boolean
  }
) {
  const { data } = await apiClient.patch<{ success: boolean; data: AdminUser; error?: string }>(
    `/dashboard/api/admin/v1/users/${userId}/`,
    payload
  )
  return data
}

export async function transferOwnership(payload: {
  object_type: 'scrape_targets' | 'scrape_runs' | 'crawl_runs' | 'crawl_sources' | 'crawl_domains' | 'prospects' | 'leads'
  from_user_id: number
  to_user_id: number
  transfer_all?: boolean
  object_ids?: number[]
}) {
  const { data } = await apiClient.post<{ success: boolean; count: number; error?: string }>(
    '/dashboard/api/admin/v1/ownership/transfer/',
    payload
  )
  return data
}

export async function listAdminScraperTargets(params?: {
  page?: number
  page_size?: number
  enabled?: boolean
  search?: string
}) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<AdminScraperTarget> }>(
    '/dashboard/api/admin/v1/scraper/targets/',
    { params }
  )
  return data.data
}

export async function triggerAdminScraperTarget(targetId: number) {
  const { data } = await apiClient.post<{ success: boolean; message?: string; task_id?: string }>(
    `/dashboard/api/admin/v1/scraper/targets/${targetId}/trigger/`
  )
  return data
}

export async function listAdminScrapeRuns(params?: {
  page?: number
  page_size?: number
  status?: string
  target_id?: number
}) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<AdminScrapeRun> }>(
    '/dashboard/api/admin/v1/scraper/runs/',
    { params }
  )
  return data.data
}

export async function retryAdminScrapeRun(runId: number) {
  const { data } = await apiClient.post<{ success: boolean; message?: string; task_id?: string }>(
    `/dashboard/api/admin/v1/scraper/runs/${runId}/retry/`
  )
  return data
}

export async function listAdminCrawlerSources(params?: {
  page?: number
  page_size?: number
  search?: string
  source_type?: string
}) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<CrawlSource> }>(
    '/dashboard/api/admin/v1/crawler/sources/',
    { params }
  )
  return data.data
}

export async function updateAdminCrawlerSource(
  sourceId: number,
  payload: Partial<Pick<CrawlSource, 'enabled' | 'priority' | 'name' | 'discovery_query' | 'source_type'>>
) {
  const { data } = await apiClient.patch<{ success: boolean; data: CrawlSource; error?: string }>(
    `/dashboard/api/admin/v1/crawler/sources/${sourceId}/`,
    payload
  )
  return data
}

export async function listAdminCrawlerDomains(params?: {
  page?: number
  page_size?: number
  crawl_status?: string
  source_id?: number
  search?: string
}) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<CrawlDomain> }>(
    '/dashboard/api/admin/v1/crawler/domains/',
    { params }
  )
  return data.data
}

export async function triggerAdminCrawlerDomain(domainId: number) {
  const { data } = await apiClient.post<{ success: boolean; run_id: number }>(
    `/dashboard/api/admin/v1/crawler/domains/${domainId}/trigger/`
  )
  return data
}

export async function resetAdminFailedCrawlerDomains(domain_ids?: number[]) {
  const { data } = await apiClient.post<{ success: boolean; count: number; error?: string }>(
    '/dashboard/api/admin/v1/crawler/domains/reset-failed/',
    { domain_ids: domain_ids ?? [] }
  )
  return data
}

export async function listAdminCrawlerRuns(params?: {
  page?: number
  page_size?: number
  status?: string
  trigger?: string
}) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<CrawlRun> }>(
    '/dashboard/api/admin/v1/crawler/runs/',
    { params }
  )
  return data.data
}

export async function cancelAdminCrawlerRun(runId: number) {
  const { data } = await apiClient.post<{ success: boolean; message?: string; error?: string }>(
    `/dashboard/api/admin/v1/crawler/runs/${runId}/cancel/`
  )
  return data
}

export async function cancelAllAdminCrawlerRuns() {
  const { data } = await apiClient.post<{ success: boolean; cancelled: number; error?: string }>(
    '/dashboard/api/admin/v1/crawler/runs/cancel-all/'
  )
  return data
}

export async function listAdminAiSearchJobs(params?: { page?: number; page_size?: number; owner_id?: number }) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<AISearchJob> }>(
    '/dashboard/api/admin/v1/ai-search/jobs/',
    { params }
  )
  return data.data
}

export async function createAdminAiSearchJob(payload: {
  seed_topic: string
  industry?: string
  region?: string
  owner_id?: number
}) {
  const { data } = await apiClient.post<{ success: boolean; data: AISearchJob; error?: string }>(
    '/dashboard/api/admin/v1/ai-search/jobs/',
    payload
  )
  return data
}

export async function getAdminAiSearchJob(jobId: number, params?: { page?: number; page_size?: number }) {
  const { data } = await apiClient.get<{ success: boolean; data: AISearchJobDetail }>(
    `/dashboard/api/admin/v1/ai-search/jobs/${jobId}/`,
    { params }
  )
  return data.data
}

export async function promoteAdminAiSearchResult(resultId: number) {
  const { data } = await apiClient.post<{
    success: boolean
    data?: { prospect_id: number; created: boolean; result: AISearchResult }
    error?: string
  }>(`/dashboard/api/admin/v1/ai-search/results/${resultId}/promote/`)
  return data
}
