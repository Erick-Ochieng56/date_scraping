import { describe, expect, it } from 'vitest'

import { formatLeadValue, isLeadCrmReady } from '@/features/pipeline/leadUtils'
import type { Lead } from '@/shared/api/types'

const baseLead: Lead = {
  id: 1,
  prospect_id: null,
  full_name: 'Jane',
  company: 'Acme',
  email: 'jane@example.com',
  phone_raw: '+15551234',
  website: '',
  event_name: '',
  status: 'interested',
  source_name: 'manual',
  notes: '',
  lead_value: '1500.00',
  created_at: '2026-01-01T00:00:00Z',
}

describe('leadUtils', () => {
  it('detects CRM-ready leads', () => {
    expect(isLeadCrmReady(baseLead)).toBe(true)
    expect(isLeadCrmReady({ ...baseLead, email: '' })).toBe(false)
  })

  it('formats lead value', () => {
    expect(formatLeadValue('1500')).toContain('1')
    expect(formatLeadValue(null)).toBe('—')
  })
})
