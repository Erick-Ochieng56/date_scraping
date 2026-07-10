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

export type ScrapeSession = {
  id: number
  status: string
  status_display: string
  started_at: string
  finished_at: string | null
  ends_at: string | null
  duration_minutes: number | null
  cycles_completed: number
  last_cycle_at: string | null
  time_remaining_seconds: number | null
  is_session_active: boolean
  targets_enqueued: number
  coordinator_task_id?: string
  error_text: string
  stats: Record<string, unknown>
  owner_id: number
  owner_username?: string
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

export type CrawlSessionPreset = '30m' | '1h' | '3h' | '6h' | '12h' | '24h'

export type CrawlSchedule = {
  id: number
  name: string
  enabled: boolean
  interval_minutes: number
  session_duration_minutes: number | null
  last_started_at: string | null
  source_filter: Record<string, unknown>
  created_at: string
  updated_at: string
  owner_id: number
  owner_username?: string
  is_due: boolean
  next_run_at: string | null
}

export type CrawlRun = {
  id: number
  trigger: string
  status: string
  status_display: string
  started_at: string
  finished_at: string | null
  ends_at?: string | null
  duration_minutes?: number | null
  cycles_completed?: number
  last_cycle_at?: string | null
  time_remaining_seconds?: number | null
  is_session_active?: boolean
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
  prospect_id: number | null
  processed_at: string | null
  updated_at: string
  contact_emails: string[]
  contact_phones: string[]
  event_names: string[]
  org_name: string
  org_type: string
}

export type EventProspect = {
  id: number
  event_name: string
  event_type: string
  organizer_name: string
  organizer_domain: string
  event_url: string
  event_date: string | null
  event_date_raw: string
  event_location: string
  is_virtual: boolean
  is_hybrid: boolean
  languages_involved: string[]
  countries_involved: string[]
  translation_services_needed: string[]
  translation_need_score: number
  urgency_score: number
  contact_name: string
  contact_email: string
  contact_phone: string
  status: string
  notes: string
  created_at: string
  updated_at: string
}

export type Prospect = {
  id: number
  event_name: string
  company: string
  email: string | null
  phone_raw: string
  website: string
  status: string
  source_name: string
  source_url: string
  notes: string
  translation_need_score: number | null
  score_label: string | null
  score_reasoning: string
  created_at: string
  updated_at?: string
  contacted_at?: string | null
  converted_at?: string | null
  rejected_at?: string | null
}

export type Lead = {
  id: number
  prospect_id: number | null
  full_name: string
  company: string
  email: string | null
  phone_raw: string
  website: string
  event_name: string
  status: string
  source_name: string
  notes: string
  lead_value: string | null
  created_at: string
  updated_at?: string
  contacted_at?: string | null
  rejected_at?: string | null
}

export type QualityMetrics = {
  prospect_score_tiers: { high: number; medium: number; low: number; unscored: number }
  prospects_high_score_new: number
  event_prospects_new: number
  enrichment_backlog: number
  leads_ready_to_sync: number
  crawl_competitors_7d: number
  prospects_by_source: Array<{ source_name: string; count: number }>
  discovery_drops: {
    period_days: number
    ai_search_jobs_analyzed: number
    total_drops_estimated: number
    by_category: Record<string, number>
    sample_reasons: Record<string, string[]>
  }
}

export type NotificationItem = {
  id: number
  type: string
  title: string
  message: string
  read: boolean
  link_url: string
  created_at: string | null
}

export type NotificationsPayload = {
  unread_count: number
  items: NotificationItem[]
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

export type AdminCrawlSessionRun = CrawlRun & {
  owner_username?: string
  coordinator_task_id?: string
}

export type AdminScrapeSession = ScrapeSession

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

export type DuplicateMatch = {
  id: number
  company: string
  email?: string | null
  website?: string
  full_name?: string
  status: string
  match_reason: string
  created_at: string | null
}

export type AdminSettingsThreshold = {
  id: string
  label: string
  value: number
  env_var: string
  description: string
}

export type AdminSettingsStatus = {
  environment: string
  debug: boolean
  integrations: IntegrationStatus[]
  thresholds?: AdminSettingsThreshold[]
}
