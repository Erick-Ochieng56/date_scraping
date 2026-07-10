import { apiClient } from '@/lib/api/client'

import type { ApiSuccess, Paginated, ScrapeRun, ScrapeSession, Target, TargetWritePayload } from './types'

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

export async function triggerAllTargets() {
  const { data } = await apiClient.post<ApiSuccess<{ message?: string; count?: number; task_ids?: string[] }>>(
    '/dashboard/api/v1/targets/trigger/'
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

export async function startScrapeSession(body: { duration_minutes?: number; preset?: string }) {
  const { data } = await apiClient.post<
    ApiSuccess<{ session_id: number; ends_at: string; message?: string; data?: ScrapeSession }>
  >('/dashboard/api/v1/scrape-sessions/', body)
  return data
}

export async function getActiveScrapeSession(): Promise<ScrapeSession | null> {
  const { data } = await apiClient.get<{ success: boolean; data: ScrapeSession | null }>(
    '/dashboard/api/v1/scrape-sessions/active/'
  )
  return data.data
}

export async function stopScrapeSession(sessionId: number) {
  const { data } = await apiClient.post<ApiSuccess<{ message?: string }>>(
    `/dashboard/api/v1/scrape-sessions/${sessionId}/stop/`
  )
  return data
}
