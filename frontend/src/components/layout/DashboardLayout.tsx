import { Outlet } from 'react-router-dom'

import { AppSidebar } from '@/components/layout/AppSidebar'
import { AppShell } from '@/shared/layouts/AppShell'

export function DashboardLayout() {
  return (
    <AppShell headerTitle="Scraper dashboard" renderSidebar={({ onNavigate }) => <AppSidebar onNavigate={onNavigate} />}>
      <Outlet />
    </AppShell>
  )
}
