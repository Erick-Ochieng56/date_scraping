import { apiClient } from '@/lib/api/client'

export type ApiSuccess<T> = T & { success?: boolean }

export type Paginated<T> = {
  items: T[]
  page: number
  page_size: number
  total: number
  has_next: boolean
}

export type Target = {
  id: number
  name: string
  enabled: boolean
  target_type: string
  start_url: string
  run_every_minutes: number
  config?: Record<string, unknown>
  last_run_at: string | null
  created_at?: string
  updated_at?: string
}

export type TargetWritePayload = {
  name: string
  enabled: boolean
  target_type: string
  start_url: string
  run_every_minutes: number
  config: Record<string, unknown>
}

export type ScrapeRun = {
  id: number
  target: number
  target_name: string
  trigger: string
  status: string
  status_display: string
  started_at: string
  finished_at: string | null
  task_id: string
  error_text: string
  item_count: number
  created_leads: number
  updated_leads: number
}

export type AISearchJob = {
  id: number
  owner_id: number
  owner_username?: string
  seed_topic: string
  industry: string
  region: string
  status: string
  error_text: string
  queries_generated: unknown[]
  domains_discovered: number
  prospects_created: number
  created_at: string
  updated_at: string
}

export type AISearchResult = {
  id: number
  domain: string
  source_url: string
  org_name: string
  org_type: string
  why_needs_translation: string
  international_signals: string[]
  contact_email: string
  queued_domain_id: number | null
  created_at: string
}

export type AISearchJobDetail = {
  job: AISearchJob
  results: Paginated<AISearchResult>
}

export type CrawlRun = {
  id: number
  trigger: string
  status: string
  status_display: string
  started_at: string
  finished_at: string | null
  task_id: string
  error_text: string
  domains_queued: number
  prospects_created: number
  prospects_updated: number
  owner_id?: number | null
  summary?: {
    total_domains: number
    failed_domains: number
    prospects_created: number
    prospects_updated: number
  }
}

export type CrawlSource = {
  id: number
  name: string
  discovery_query: string
  source_type: string
  enabled: boolean
  priority: number
  created_at: string
  owner_id?: number | null
}

export type CrawlDomain = {
  id: number
  domain: string
  /** Serp / manual landing URL; crawler visits this first when set. */
  source_url?: string
  source: number | null
  source_name: string
  crawl_status: string
  crawl_attempts: number
  priority: number
  first_seen_at: string
  last_crawled_at: string | null
  next_attempt_at: string | null
  error_text: string
  owner_id?: number | null
}

export type CrawlerDiscoveryHit = {
  domain: string
  source_url: string
}

export type CrawlerPreviewResponse = {
  success: boolean
  hits?: CrawlerDiscoveryHit[]
  urls: string[]
}

export type CrawlRunDomainResult = {
  id: number
  domain: number
  domain_name: string
  state: string
  crawl_succeeded: boolean
  crawl_error: string
  pages_crawled: number
  score: number
  score_label: string
  prospect_created: boolean
  prospect_updated: boolean
  processed_at: string | null
  updated_at: string
  contact_emails: string[]
  contact_phones: string[]
  event_names: string[]
  org_name: string
  org_type: string
}

export type Prospect = {
  id: number
  event_name: string
  company: string
  email: string | null
  phone_raw: string
  website: string
  status: string
  created_at: string
}

export type Lead = {
  id: number
  full_name: string
  company: string
  email: string | null
  phone_raw: string
  website: string
  event_name: string
  status: string
  created_at: string
}

export type MetricsSummary = {
  targets_enabled: number
  scrape_runs_recent: number
  scrape_success_recent: number
  crawl_runs_recent: number
  failed_crawls_recent?: number
  prospects_new: number
  prospects_contacted: number
  leads_interested: number
  leads_synced: number
  prospect_status_breakdown: Array<{ status: string; count: number }>
  lead_status_breakdown: Array<{ status: string; count: number }>
}

export type AdminUser = {
  id: number
  username: string
  email: string
  is_active: boolean
  is_superuser: boolean
  is_staff: boolean
  role: 'admin' | 'staff' | 'none'
  groups: string[]
  last_login: string | null
  date_joined: string | null
}

export type AdminScraperTarget = {
  id: number
  name: string
  enabled: boolean
  target_type: string
  start_url: string
  run_every_minutes: number
  last_run_at: string | null
  owner_id: number | null
}

export type AdminScrapeRun = {
  id: number
  target: number
  target_name: string
  trigger: string
  status: string
  status_display: string
  started_at: string | null
  finished_at: string | null
  task_id: string
  error_text: string
  item_count: number
  created_leads: number
  updated_leads: number
  owner_id: number | null
}

export async function triggerScrape(targetId?: number) {
  const { data } = await apiClient.post<ApiSuccess<{ message?: string; task_id?: string }>>(
    '/dashboard/api/trigger-scrape/',
    targetId != null ? { target_id: targetId } : {}
  )
  return data
}

export async function getRunStatus(runId: number) {
  const { data } = await apiClient.get(`/dashboard/api/runs/${runId}/status/`)
  return data
}

export async function retryRun(runId: number) {
  const { data } = await apiClient.post<ApiSuccess<{ message?: string }>>(
    `/dashboard/api/runs/${runId}/retry/`
  )
  return data
}

export async function listTargets(params?: { enabled?: boolean; page?: number; page_size?: number }) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<Target> }>('/dashboard/api/v1/targets/', {
    params,
  })
  return data.data
}

export async function triggerTarget(targetId: number) {
  const { data } = await apiClient.post<ApiSuccess<{ message?: string; task_id?: string }>>(
    `/dashboard/api/v1/targets/${targetId}/trigger/`
  )
  return data
}

export async function getTarget(targetId: number) {
  const { data } = await apiClient.get<{ success: boolean; data: Target }>(`/dashboard/api/v1/targets/${targetId}/`)
  return data.data
}

export async function createTarget(payload: TargetWritePayload) {
  const { data } = await apiClient.post<{ success: boolean; data: Target }>('/dashboard/api/v1/targets/', payload)
  return data.data
}

export async function updateTarget(targetId: number, payload: Partial<TargetWritePayload>) {
  const { data } = await apiClient.patch<{ success: boolean; data: Target }>(
    `/dashboard/api/v1/targets/${targetId}/`,
    payload
  )
  return data.data
}

export async function listScrapeRuns(params?: {
  page?: number
  page_size?: number
  status?: string
  target_id?: number
}) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<ScrapeRun> }>(
    '/dashboard/api/v1/scrape-runs/',
    { params }
  )
  return data.data
}

export async function getScrapeRun(runId: number) {
  const { data } = await apiClient.get<{ success: boolean; data: ScrapeRun }>(`/dashboard/api/v1/scrape-runs/${runId}/`)
  return data.data
}

export async function retryScrapeRun(runId: number) {
  const { data } = await apiClient.post<ApiSuccess<{ message?: string; task_id?: string }>>(
    `/dashboard/api/v1/scrape-runs/${runId}/retry/`
  )
  return data
}

export async function listCrawlRuns(params?: { page?: number; page_size?: number; status?: string; trigger?: string }) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<CrawlRun> }>(
    '/dashboard/api/v1/crawl-runs/',
    { params }
  )
  return data.data
}

export async function triggerCrawler() {
  const { data } = await apiClient.post<ApiSuccess<{ message?: string; task_id?: string }>>(
    '/dashboard/api/v1/crawl-runs/trigger/'
  )
  return data
}

export async function cancelCrawlRun(runId: number) {
  const { data } = await apiClient.post<ApiSuccess<{ message?: string }>>(
    `/dashboard/api/v1/crawl-runs/${runId}/cancel/`
  )
  return data
}

export async function cancelAllRunningCrawls() {
  const { data } = await apiClient.post<ApiSuccess<{ cancelled: number }>>('/dashboard/api/v1/crawl-runs/cancel-all/')
  return data
}

export async function getCrawlRun(runId: number) {
  const { data } = await apiClient.get<{ success: boolean; data: CrawlRun }>(`/dashboard/api/v1/crawl-runs/${runId}/`)
  return data.data
}

export async function listCrawlRunDomainResults(
  runId: number,
  params?: { page?: number; page_size?: number; state?: string; errors_only?: boolean }
) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<CrawlRunDomainResult> }>(
    `/dashboard/api/v1/crawl-runs/${runId}/domains/`,
    { params }
  )
  return data.data
}

export async function listCrawlSources(params?: { page?: number; page_size?: number; source_type?: string }) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<CrawlSource> }>(
    '/dashboard/api/v1/crawl-sources/',
    { params }
  )
  return data.data
}

export async function listCrawlDomains(params?: {
  page?: number
  page_size?: number
  crawl_status?: string
  search?: string
}) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<CrawlDomain> }>(
    '/dashboard/api/v1/crawl-domains/',
    { params }
  )
  return data.data
}

export async function triggerCrawlDomain(domainId: number) {
  const { data } = await apiClient.post<ApiSuccess<{ run_id: number }>>(
    `/dashboard/api/v1/crawl-domains/${domainId}/trigger/`
  )
  return data
}

export async function crawlerPreview(query: string, max_results = 20): Promise<CrawlerPreviewResponse> {
  const { data } = await apiClient.post<CrawlerPreviewResponse>('/dashboard/api/crawler/preview/', {
    query,
    max_results,
  })
  return data
}

export async function crawlerQueue(payload: { query: string; max_results?: number; auto_crawl?: boolean; urls?: string[] }) {
  const { data } = await apiClient.post<{
    success: boolean
    queued: number
    new_domains: number
    run_id: number | null
    domain_ids: number[]
  }>('/dashboard/api/crawler/queue/', payload)
  return data
}

export async function listProspects(params?: { page?: number; page_size?: number; status?: string; search?: string }) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<Prospect> }>('/dashboard/api/v1/prospects/', {
    params,
  })
  return data.data
}

export async function prospectsBulkContacted(prospect_ids: number[]) {
  const { data } = await apiClient.post<{ success: boolean; count: number }>(
    '/dashboard/api/v1/prospects/bulk/contacted/',
    { prospect_ids }
  )
  return data
}

export async function prospectsBulkConvert(prospect_ids: number[]) {
  const { data } = await apiClient.post<{ success: boolean; count: number; errors?: string[] }>(
    '/dashboard/api/v1/prospects/bulk/convert/',
    { prospect_ids }
  )
  return data
}

export async function prospectsBulkReject(prospect_ids: number[]) {
  const { data } = await apiClient.post<{ success: boolean; count: number }>(
    '/dashboard/api/v1/prospects/bulk/reject/',
    { prospect_ids }
  )
  return data
}

export async function getProspect(prospectId: number) {
  const { data } = await apiClient.get<{ success: boolean; data: Prospect }>(`/dashboard/api/v1/prospects/${prospectId}/`)
  return data.data
}

export async function prospectMarkContacted(prospectId: number) {
  const { data } = await apiClient.post<{ success: boolean }>(`/dashboard/api/v1/prospects/${prospectId}/mark-contacted/`)
  return data
}

export async function prospectConvert(prospectId: number) {
  const { data } = await apiClient.post<{ success: boolean; lead_id?: number }>(`/dashboard/api/v1/prospects/${prospectId}/convert/`)
  return data
}

export async function prospectReject(prospectId: number, reason?: string) {
  const { data } = await apiClient.post<{ success: boolean }>(`/dashboard/api/v1/prospects/${prospectId}/reject/`, {
    reason,
  })
  return data
}

export async function listLeads(params?: { page?: number; page_size?: number; status?: string; search?: string }) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<Lead> }>('/dashboard/api/v1/leads/', {
    params,
  })
  return data.data
}

export async function leadsBulkInterested(lead_ids: number[]) {
  const { data } = await apiClient.post<{ success: boolean; count: number }>(
    '/dashboard/api/v1/leads/bulk/interested/',
    { lead_ids }
  )
  return data
}

export async function leadsBulkReject(lead_ids: number[]) {
  const { data } = await apiClient.post<{ success: boolean; count: number }>(
    '/dashboard/api/v1/leads/bulk/reject/',
    { lead_ids }
  )
  return data
}

export async function getLead(leadId: number) {
  const { data } = await apiClient.get<{ success: boolean; data: Lead }>(`/dashboard/api/v1/leads/${leadId}/`)
  return data.data
}

export async function leadMarkInterested(leadId: number) {
  const { data } = await apiClient.post<{ success: boolean }>(`/dashboard/api/v1/leads/${leadId}/mark-interested/`)
  return data
}

export async function leadReject(leadId: number) {
  const { data } = await apiClient.post<{ success: boolean }>(`/dashboard/api/v1/leads/${leadId}/reject/`)
  return data
}

export async function leadSyncCrm(leadId: number) {
  const { data } = await apiClient.post<{ success: boolean; task_id?: string }>(`/dashboard/api/v1/leads/${leadId}/sync-crm/`)
  return data
}

export async function fetchMetricsSummary() {
  const { data } = await apiClient.get<{ success: boolean; data: MetricsSummary }>('/dashboard/api/v1/metrics/summary/')
  return data.data
}

export type RunsStreamPayload = {
  scrape_runs: Array<Record<string, unknown>>
  crawl_runs: Array<Record<string, unknown>>
}

export function subscribeRunsStream(
  onData: (payload: RunsStreamPayload) => void,
  onFallbackNeeded: () => void
) {
  const streamBase = `${window.location.origin}/dashboard/api/v1/stream/runs/`
  const es = new EventSource(streamBase, { withCredentials: true })
  es.addEventListener('runs', (event) => {
    try {
      const payload = JSON.parse((event as MessageEvent).data) as RunsStreamPayload
      onData(payload)
    } catch {
      // Ignore malformed events.
    }
  })
  es.onerror = () => {
    es.close()
    onFallbackNeeded()
  }
  return () => es.close()
}

export async function fetchNotifications() {
  const { data } = await apiClient.get('/dashboard/api/notifications/')
  return data
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

export async function listAdminScraperTargets(params?: { page?: number; page_size?: number; enabled?: boolean; search?: string }) {
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

export async function listAdminScrapeRuns(params?: { page?: number; page_size?: number; status?: string; target_id?: number }) {
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

export async function listAdminCrawlerSources(params?: { page?: number; page_size?: number; search?: string; source_type?: string }) {
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

export async function listAdminCrawlerRuns(params?: { page?: number; page_size?: number; status?: string; trigger?: string }) {
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

export async function listAiSearchJobs(params?: { page?: number; page_size?: number }) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<AISearchJob> }>(
    '/dashboard/api/v1/ai-search/jobs/',
    { params }
  )
  return data.data
}

export async function createAiSearchJob(payload: { seed_topic: string; industry?: string; region?: string }) {
  const { data } = await apiClient.post<{ success: boolean; data: AISearchJob; error?: string }>(
    '/dashboard/api/v1/ai-search/jobs/',
    payload
  )
  return data
}

export async function getAiSearchJob(jobId: number, params?: { page?: number; page_size?: number }) {
  const { data } = await apiClient.get<{ success: boolean; data: AISearchJobDetail }>(
    `/dashboard/api/v1/ai-search/jobs/${jobId}/`,
    { params }
  )
  return data.data
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
  /** When omitted, the job is owned by the admin (domains queue under their account). */
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
