import { describe, expect, it } from 'vitest'

import { router } from '@/app/router'

describe('app router', () => {
  it('registers staff, admin, and login routes', () => {
    const paths = router.routes.map((r) => r.path)
    expect(paths).toContain('/login')
    expect(paths).toContain('/')
    expect(paths).toContain('/admin')
  })

  it('exposes a top-level /find-leads hub and keeps the old crawler/ai-search path as a redirect', () => {
    const staffRoute = router.routes.find((r) => r.path === '/')
    const staffChildren = staffRoute?.children ?? []
    expect(staffChildren.some((c) => c.path === 'find-leads')).toBe(true)

    const crawlerRoute = staffChildren.find((c) => c.path === 'crawler')
    const aiSearchRedirect = crawlerRoute?.children?.find((c) => c.path === 'ai-search')
    expect(aiSearchRedirect).toBeTruthy()
  })
})
