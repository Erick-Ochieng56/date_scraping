import { apiClient } from '@/lib/api/client'

import type {
  AISearchJob,
  AISearchJobDetail,
  ApiSuccess,
  CrawlerPreviewResponse,
  CrawlDomain,
  CrawlRun,
  CrawlRunDomainResult,
  CrawlSource,
  Paginated,
} from './types'

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

export async function crawlerQueue(payload: {
  query: string
  max_results?: number
  auto_crawl?: boolean
  urls?: string[]
}) {
  const { data } = await apiClient.post<{
    success: boolean
    queued: number
    new_domains: number
    run_id: number | null
    domain_ids: number[]
  }>('/dashboard/api/crawler/queue/', payload)
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
