export type CrawlSessionPreset = '30m' | '1h' | '3h' | '6h' | '12h' | '24h'

export const CRAWL_SESSION_MIN_MINUTES = 15
export const CRAWL_SESSION_MAX_MINUTES = 1440

export const CRAWL_SESSION_PRESETS: { value: CrawlSessionPreset; label: string; minutes: number }[] = [
  { value: '30m', label: '30 minutes', minutes: 30 },
  { value: '1h', label: '1 hour', minutes: 60 },
  { value: '3h', label: '3 hours', minutes: 180 },
  { value: '6h', label: '6 hours', minutes: 360 },
  { value: '12h', label: '12 hours', minutes: 720 },
  { value: '24h', label: '24 hours', minutes: 1440 },
]

export function formatDurationMinutes(minutes: number): string {
  if (minutes >= 60 && minutes % 60 === 0) {
    const h = minutes / 60
    return `${h}h`
  }
  return `${minutes}m`
}

export function formatTimeRemaining(seconds: number | null | undefined): string {
  if (seconds == null || seconds <= 0) return '0m'
  const h = Math.floor(seconds / 3600)
  const m = Math.floor((seconds % 3600) / 60)
  if (h > 0) return `${h}h ${m}m`
  return `${m}m`
}
