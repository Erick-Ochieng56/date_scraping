import { useEffect, useState } from 'react'
import { useQueryClient } from '@tanstack/react-query'

import { subscribeRunsStream } from '@/shared/api/metrics'

/** Live scrape/crawl run updates via SSE; falls back to polling-only when the stream is unavailable. */
export function useRunsStream(enabled = true) {
  const qc = useQueryClient()
  const [transport, setTransport] = useState<'sse' | 'polling'>('sse')

  useEffect(() => {
    if (!enabled) return

    const invalidateRunQueries = () => {
      void qc.invalidateQueries({ queryKey: ['scrape-runs'] })
      void qc.invalidateQueries({ queryKey: ['crawler', 'runs'] })
      void qc.invalidateQueries({ queryKey: ['metrics-summary'] })
      void qc.invalidateQueries({ queryKey: ['admin', 'metrics'] })
    }

    const unsubscribe = subscribeRunsStream(invalidateRunQueries, () => setTransport('polling'))
    return unsubscribe
  }, [enabled, qc])

  return { transport }
}
