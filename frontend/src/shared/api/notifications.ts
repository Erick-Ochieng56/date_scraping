import { apiClient } from '@/lib/api/client'

import type { NotificationsPayload } from './types'

export async function fetchNotifications(params?: { limit?: number }) {
  const { data } = await apiClient.get<{ success: boolean; data: NotificationsPayload }>(
    '/dashboard/api/v1/notifications/',
    { params }
  )
  return data.data
}

export async function markNotificationRead(notifId: number) {
  const { data } = await apiClient.post<{ success: boolean }>(`/dashboard/api/v1/notifications/${notifId}/read/`)
  return data
}

export async function markAllNotificationsRead() {
  const { data } = await apiClient.post<{ success: boolean; marked: number }>(
    '/dashboard/api/v1/notifications/read-all/'
  )
  return data
}
