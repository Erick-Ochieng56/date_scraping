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
  promoted_prospect_id: number | null
  translation_need_score: number | null
  evidence_snippet: string
  buyer_signal_type: string
  action_date: string
  promotable: boolean
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
  drop_reason?: string
}

export type CrawlerPreviewResponse = {
  success: boolean
  hits?: CrawlerDiscoveryHit[]
  urls: string[]
  dropped?: CrawlerDiscoveryHit[]
  dropped_count?: number
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
  event_date: string | null
  company: string
  email: string | null
  phone_raw: string
  website: string
  status: string
  source_name: string
  source_url: string
  notes: string
  created_at: string
  updated_at: string
  contacted_at: string | null
  converted_at: string | null
  rejected_at: string | null
}

export type ProspectDetail = Prospect & {
  raw_payload: Record<string, unknown>
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
  prospects_contacted_recent?: number
  leads_interested: number
  leads_synced: number
  prospect_status_breakdown: Array<{ status: string; count: number }>
  lead_status_breakdown: Array<{ status: string; count: number }>
}

export type MetricsGranularity = 'day' | 'week' | 'month'

export type ProspectSourceBreakdown = {
  ai_search: number
  web_crawler: number
  site_check: number
}

export type MetricsTimeseriesBucket = {
  date: string
  prospects_total: number
  prospects_by_source: ProspectSourceBreakdown
  leads_created: number
}

export type MetricsTimeseries = {
  granularity: MetricsGranularity
  periods: number
  buckets: MetricsTimeseriesBucket[]
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

export type RunsStreamPayload = {
  scrape_runs: Array<Record<string, unknown>>
  crawl_runs: Array<Record<string, unknown>>
}

export type ActivityLogEntry = {
  id: number
  created_at: string | null
  user_id: number | null
  username: string | null
  action: string
  action_display: string
  object_type: string
  object_id: number
  description: string
  metadata: Record<string, unknown>
}

export type ActivityLogFilters = {
  actions: Array<{ value: string; label: string }>
}

export type IntegrationStatus = {
  id: string
  label: string
  enabled: boolean
  configured: boolean
  status: string
  hint: string
}

export type AdminSettingsStatus = {
  environment: string
  debug: boolean
  integrations: IntegrationStatus[]
}
