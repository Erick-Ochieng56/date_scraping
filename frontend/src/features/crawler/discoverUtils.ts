import type { CrawlerDiscoveryHit } from '@/shared/api/types'

export type PreviewRow = {
  id: string
  domain: string
  landing: string
}

export const DISCOVER_EXAMPLE_QUERIES = [
  'translation conference Europe',
  'NGO language services Africa',
  'international association annual meeting',
] as const

export const DISCOVER_MAX_OPTIONS = [10, 20, 30, 50] as const

export function normalizeDiscoveryEntry(raw: string): string {
  const value = raw.trim()
  if (!value) return ''
  const candidate = /^https?:\/\//i.test(value) ? value : `https://${value}`
  try {
    const u = new URL(candidate)
    if (!u.hostname) return ''
    const path = u.pathname || ''
    const hasPath = path.length > 1
    const hasQuery = (u.search || '').length > 1
    if (hasPath || hasQuery) {
      let out = `${u.origin}${path}${u.search || ''}`
      if (out.endsWith('/') && path !== '/' && path.length > 1) {
        out = out.replace(/\/+$/, '')
      }
      return out
    }
    return `${u.origin}`
  } catch {
    return ''
  }
}

export function hitsToRows(hits: CrawlerDiscoveryHit[]): PreviewRow[] {
  return hits.map((h, i) => {
    const landing = (h.source_url || h.domain || '').trim()
    let domain = (h.domain || '').trim()
    if (!domain && landing) {
      try {
        domain = new URL(landing).origin
      } catch {
        domain = landing
      }
    }
    return {
      id: landing || `${domain}-${i}`,
      domain,
      landing,
    }
  })
}

export function urlsToRows(urls: string[]): PreviewRow[] {
  return urls.map((u, i) => {
    const landing = u.trim()
    let domain = landing
    try {
      domain = new URL(landing).origin
    } catch {
      /* keep */
    }
    return { id: landing || `row-${i}`, domain, landing }
  })
}
