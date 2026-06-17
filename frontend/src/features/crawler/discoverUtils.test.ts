import { describe, expect, it } from 'vitest'

import { normalizeDiscoveryEntry } from '@/features/crawler/discoverUtils'

describe('normalizeDiscoveryEntry', () => {
  it('keeps deep links with path', () => {
    expect(normalizeDiscoveryEntry('example.org/events/summit')).toBe('https://example.org/events/summit')
  })

  it('normalizes bare domains to origin', () => {
    expect(normalizeDiscoveryEntry('https://example.org')).toBe('https://example.org')
  })

  it('returns empty for invalid input', () => {
    expect(normalizeDiscoveryEntry('   ')).toBe('')
  })
})
