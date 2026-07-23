import type { ProspectDetail } from '@/shared/api/types'

export type ProspectSource = 'ai_search' | 'web_crawler' | 'site_check'

export function classifyProspectSource(sourceName: string): ProspectSource {
  if (sourceName === 'ai_search') return 'ai_search'
  if (sourceName === 'web_crawler') return 'web_crawler'
  return 'site_check'
}

export const SOURCE_META: Record<ProspectSource, { label: string; textClass: string; softClass: string }> = {
  ai_search: { label: 'AI search', textClass: 'text-chart-1', softClass: 'bg-chart-1/10' },
  web_crawler: { label: 'Web crawler', textClass: 'text-chart-2', softClass: 'bg-chart-2/10' },
  site_check: { label: 'Site check', textClass: 'text-chart-3', softClass: 'bg-chart-3/10' },
}

export type MatchLabel = 'Strong match' | 'Possible match' | 'Weak match'

/** Mirrors backend/crawler/scoring.py get_score_label thresholds. */
export function matchLabelFromScore(score: number): MatchLabel {
  if (score > 60) return 'Strong match'
  if (score > 30) return 'Possible match'
  return 'Weak match'
}

export type ProspectEvidence = {
  source: ProspectSource
  sourceLabel: string
  score: number | null
  matchLabel: MatchLabel | null
  evidenceText: string | null
  signals: string[]
}

function toNumber(v: unknown): number | null {
  const n = typeof v === 'number' ? v : typeof v === 'string' ? Number(v) : NaN
  return Number.isFinite(n) ? n : null
}

function toText(v: unknown): string | null {
  if (typeof v !== 'string') return null
  const trimmed = v.trim()
  return trimmed ? trimmed : null
}

function toStringArray(v: unknown, limit = 4): string[] {
  if (!Array.isArray(v)) return []
  return v.filter((x): x is string => typeof x === 'string' && x.trim() !== '').slice(0, limit)
}

/**
 * Builds a plain-language "why was this found" summary from whatever the
 * originating pipeline actually captured in raw_payload — never fabricated.
 * Site checks have no scoring concept, so score/matchLabel stay null there.
 */
export function getProspectEvidence(prospect: ProspectDetail): ProspectEvidence {
  const source = classifyProspectSource(prospect.source_name)
  const payload = prospect.raw_payload ?? {}
  const sourceLabel = SOURCE_META[source].label

  if (source === 'ai_search') {
    const score = toNumber(payload.translation_need_score)
    return {
      source,
      sourceLabel,
      score,
      matchLabel: score == null ? null : matchLabelFromScore(score),
      evidenceText: toText(payload.evidence_snippet) ?? toText(payload.why_needs_translation),
      signals: toStringArray(payload.international_signals),
    }
  }

  if (source === 'web_crawler') {
    const score = toNumber(payload.translation_need_score)
    const services = toStringArray(payload.detected_services)
    const languages = toStringArray(payload.languages_detected)
    const evidenceParts: string[] = []
    if (services.length) evidenceParts.push(`Detected services: ${services.join(', ')}`)
    if (languages.length) evidenceParts.push(`Languages detected: ${languages.join(', ')}`)
    return {
      source,
      sourceLabel,
      score,
      matchLabel: score == null ? null : matchLabelFromScore(score),
      evidenceText: evidenceParts.length ? evidenceParts.join(' — ') : null,
      signals: toStringArray(payload.international_signals),
    }
  }

  return {
    source: 'site_check',
    sourceLabel,
    score: null,
    matchLabel: null,
    evidenceText: prospect.source_name ? `Found on a scheduled check of ${prospect.source_name}.` : null,
    signals: [],
  }
}
