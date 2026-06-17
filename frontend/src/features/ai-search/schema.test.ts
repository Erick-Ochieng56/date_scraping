import { describe, expect, it } from 'vitest'

import { aiSearchFormSchema } from '@/features/ai-search/schema'

describe('aiSearchFormSchema', () => {
  it('requires seed topic', () => {
    const result = aiSearchFormSchema.safeParse({ seedTopic: '  ' })
    expect(result.success).toBe(false)
  })

  it('accepts optional industry and region', () => {
    const result = aiSearchFormSchema.safeParse({
      seedTopic: 'translation conferences',
      industry: 'NGO',
      region: 'Kenya',
    })
    expect(result.success).toBe(true)
  })
})
