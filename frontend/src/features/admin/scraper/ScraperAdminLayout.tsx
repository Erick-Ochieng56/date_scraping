import { Outlet } from 'react-router-dom'

import { ScraperAdminSubNav } from '@/features/admin/scraper/ScraperAdminSubNav'

export function ScraperAdminLayout() {
  return (
    <div className="space-y-4">
      <ScraperAdminSubNav />
      <Outlet />
    </div>
  )
}
