import { apiClient } from '@/lib/api/client'

import type { MetricsSummary, QualityMetrics, RunsStreamPayload } from './types'

export { fetchNotifications, markAllNotificationsRead, markNotificationRead } from './notifications'

export async function fetchMetricsSummary() {
  const { data } = await apiClient.get<{ success: boolean; data: MetricsSummary }>('/dashboard/api/v1/metrics/summary/')
  return data.data
}

export async function fetchQualityMetrics() {
  const { data } = await apiClient.get<{ success: boolean; data: QualityMetrics }>('/dashboard/api/v1/metrics/quality/')
  return data.data
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
