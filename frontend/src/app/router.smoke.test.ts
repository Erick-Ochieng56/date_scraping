import { describe, expect, it } from 'vitest'

import { router } from '@/app/router'

describe('app router', () => {
  it('registers staff, admin, and login routes', () => {
    const paths = router.routes.map((r) => r.path)
    expect(paths).toContain('/login')
    expect(paths).toContain('/')
    expect(paths).toContain('/admin')
  })
})
