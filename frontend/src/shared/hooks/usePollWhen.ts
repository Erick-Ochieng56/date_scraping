/** Poll interval when any record or a single status is "running". */
export function pollIntervalWhenRunning(
  status: string | undefined,
  items: Array<{ status: string }> | undefined,
  intervalMs = 5000
): number | false {
  if (status === 'running') return intervalMs
  if (items?.some((r) => r.status === 'running')) return intervalMs
  return false
}
