import { Outlet } from 'react-router-dom'

import { CrawlerSubNav } from '@/features/crawler/CrawlerSubNav'

export function CrawlerLayout() {
  return (
    <div className="space-y-4">
      <CrawlerSubNav />
      <Outlet />
    </div>
  )
}
