import { describe, expect, it } from 'vitest'

import { getProspectEvidence, matchLabelFromScore } from '@/features/pipeline/evidence'
import type { ProspectDetail } from '@/shared/api/types'

function makeProspect(overrides: Partial<ProspectDetail>): ProspectDetail {
  return {
    id: 1,
    event_name: '',
    event_date: null,
    company: 'Acme',
    email: null,
    phone_raw: '',
    website: '',
    status: 'new',
    source_name: '',
    source_url: '',
    notes: '',
    created_at: '2026-01-01T00:00:00Z',
    updated_at: '2026-01-01T00:00:00Z',
    contacted_at: null,
    converted_at: null,
    rejected_at: null,
    raw_payload: {},
    ...overrides,
  }
}

describe('matchLabelFromScore', () => {
  it('mirrors backend get_score_label thresholds', () => {
    expect(matchLabelFromScore(80)).toBe('Strong match')
    expect(matchLabelFromScore(61)).toBe('Strong match')
    expect(matchLabelFromScore(60)).toBe('Possible match')
    expect(matchLabelFromScore(31)).toBe('Possible match')
    expect(matchLabelFromScore(30)).toBe('Weak match')
    expect(matchLabelFromScore(0)).toBe('Weak match')
  })
})

describe('getProspectEvidence', () => {
  it('reads AI search evidence and score from raw_payload', () => {
    const evidence = getProspectEvidence(
      makeProspect({
        source_name: 'ai_search',
        raw_payload: {
          translation_need_score: 75,
          evidence_snippet: 'Tender notice for interpretation services.',
          international_signals: ['multilingual delegates', 'EN/FR/SW'],
        },
      })
    )
    expect(evidence.source).toBe('ai_search')
    expect(evidence.score).toBe(75)
    expect(evidence.matchLabel).toBe('Strong match')
    expect(evidence.evidenceText).toBe('Tender notice for interpretation services.')
    expect(evidence.signals).toEqual(['multilingual delegates', 'EN/FR/SW'])
  })

  it('composes web crawler evidence from detected signals', () => {
    const evidence = getProspectEvidence(
      makeProspect({
        source_name: 'web_crawler',
        raw_payload: {
          translation_need_score: 45,
          detected_services: ['conference interpretation'],
          languages_detected: ['English', 'French'],
        },
      })
    )
    expect(evidence.source).toBe('web_crawler')
    expect(evidence.matchLabel).toBe('Possible match')
    expect(evidence.evidenceText).toBe('Detected services: conference interpretation — Languages detected: English, French')
  })

  it('has no score or evidence for site checks, but names the site', () => {
    const evidence = getProspectEvidence(makeProspect({ source_name: 'Eventbrite Nairobi', raw_payload: {} }))
    expect(evidence.source).toBe('site_check')
    expect(evidence.score).toBeNull()
    expect(evidence.matchLabel).toBeNull()
    expect(evidence.evidenceText).toBe('Found on a scheduled check of Eventbrite Nairobi.')
  })

  it('does not fabricate a score when raw_payload lacks one', () => {
    const evidence = getProspectEvidence(makeProspect({ source_name: 'ai_search', raw_payload: {} }))
    expect(evidence.score).toBeNull()
    expect(evidence.matchLabel).toBeNull()
    expect(evidence.evidenceText).toBeNull()
  })
})
