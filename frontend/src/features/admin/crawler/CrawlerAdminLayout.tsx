import { Outlet } from 'react-router-dom'

import { CrawlerAdminSubNav } from '@/features/admin/crawler/CrawlerAdminSubNav'

export function CrawlerAdminLayout() {
  return (
    <div className="space-y-4">
      <CrawlerAdminSubNav />
      <Outlet />
    </div>
  )
}
