import type { Target, TargetWritePayload } from '@/shared/api/types'

export function targetTypeLabel(v: string) {
  if (v === 'html') return 'HTML'
  if (v === 'playwright') return 'Playwright'
  return v
}

export function targetTypeLabelLong(v: string) {
  if (v === 'html') return 'HTML (requests)'
  if (v === 'playwright') return 'Playwright (browser)'
  return v
}

export function hasItemSelector(config: Target['config'] | undefined): boolean {
  if (!config || typeof config !== 'object') return false
  const sel = config.item_selector ?? config.items_selector
  return typeof sel === 'string' && sel.length > 0
}

/** Matches `scraper.services.runner.run_target` — adjust selectors for your listing page. */
export const DEFAULT_TARGET_CONFIG_JSON = `{
  "item_selector": "article, .listing-item, tr",
  "fields": {
    "title": "h2 a, h3 a, h2, h3",
    "url": { "selector": "a", "attr": "href" }
  },
  "max_pages": 1
}`

export function parseConfigJson(
  raw: string
): { ok: true; value: Record<string, unknown> } | { ok: false; message: string } {
  try {
    const v = JSON.parse(raw) as unknown
    if (v === null || typeof v !== 'object' || Array.isArray(v)) {
      return { ok: false, message: 'Config must be a JSON object.' }
    }
    return { ok: true, value: v as Record<string, unknown> }
  } catch {
    return { ok: false, message: 'Invalid JSON in configuration.' }
  }
}

export function buildTargetPayload(
  fields: {
    name: string
    startUrl: string
    targetType: string
    enabled: boolean
    runEvery: number
    configJson: string
  },
  setError: (msg: string) => void
): TargetWritePayload | null {
  const trimmedName = fields.name.trim()
  if (!trimmedName) {
    setError('Name is required.')
    return null
  }
  const trimmedUrl = fields.startUrl.trim()
  if (!trimmedUrl) {
    setError('Start URL is required.')
    return null
  }
  const parsed = parseConfigJson(fields.configJson)
  if (!parsed.ok) {
    setError(parsed.message)
    return null
  }
  const itemSel = parsed.value.item_selector ?? parsed.value.items_selector
  if (!itemSel || typeof itemSel !== 'string') {
    setError('Config must include item_selector (CSS) for each row on the listing page.')
    return null
  }
  const fieldMap = parsed.value.fields
  if (!fieldMap || typeof fieldMap !== 'object' || Array.isArray(fieldMap)) {
    setError('Config must include a fields object (field name → selector or { selector, attr }).')
    return null
  }
  return {
    name: trimmedName,
    enabled: fields.enabled,
    target_type: fields.targetType,
    start_url: trimmedUrl,
    run_every_minutes: Math.max(1, Math.floor(fields.runEvery) || 60),
    config: parsed.value,
  }
}

export function filterTargets(targets: Target[], search: string): Target[] {
  const q = search.trim().toLowerCase()
  if (!q) return targets
  return targets.filter(
    (t) =>
      t.name.toLowerCase().includes(q) ||
      t.target_type.toLowerCase().includes(q) ||
      t.start_url.toLowerCase().includes(q)
  )
}

const PLATFORM_LABELS: Record<string, string> = {
  eventbrite: 'Eventbrite',
  meetup: 'Meetup',
  facebook: 'Facebook Events',
  eventful: 'Eventful',
  brownpapertickets: 'Brown Paper Tickets',
  ticketmaster: 'Ticketmaster',
  generic: 'Generic listing',
}

export function platformLabel(platform: string): string {
  return PLATFORM_LABELS[platform.toLowerCase()] ?? platform
}
