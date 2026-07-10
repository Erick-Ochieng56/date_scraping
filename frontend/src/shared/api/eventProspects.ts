import { apiClient } from '@/lib/api/client'

import type { EventProspect, Paginated } from './types'

export type EventProspectListParams = {
  page?: number
  page_size?: number
  status?: string
  search?: string
  min_score?: number
  sort?: 'urgency' | 'date' | 'score'
}

export async function listEventProspects(params?: EventProspectListParams) {
  const { data } = await apiClient.get<{ success: boolean; data: Paginated<EventProspect> }>(
    '/dashboard/api/v1/event-prospects/',
    { params }
  )
  return data.data
}

export async function getEventProspect(eventProspectId: number) {
  const { data } = await apiClient.get<{ success: boolean; data: EventProspect }>(
    `/dashboard/api/v1/event-prospects/${eventProspectId}/`
  )
  return data.data
}

export async function promoteEventProspect(eventProspectId: number) {
  const { data } = await apiClient.post<{ success: boolean; prospect_id: number; created: boolean }>(
    `/dashboard/api/v1/event-prospects/${eventProspectId}/promote/`
  )
  return data
}

export async function rejectEventProspect(eventProspectId: number, reason?: string) {
  const { data } = await apiClient.post<{ success: boolean }>(
    `/dashboard/api/v1/event-prospects/${eventProspectId}/reject/`,
    { reason }
  )
  return data
}
