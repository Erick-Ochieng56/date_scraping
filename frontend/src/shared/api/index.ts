export * from './types'
export * from './errors'
export * from './scraper'
export * from './crawler'
export * from './pipeline'
export * from './metrics'
export * from './admin'
export * from './wizard'

// Legacy endpoints kept for backward compatibility
import { apiClient } from '@/lib/api/client'

import type { ApiSuccess } from './types'

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
  const { data } = await apiClient.post<ApiSuccess<{ message?: string }>>(`/dashboard/api/runs/${runId}/retry/`)
  return data
}
