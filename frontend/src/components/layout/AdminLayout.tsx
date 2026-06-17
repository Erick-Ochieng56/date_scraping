import { Outlet } from 'react-router-dom'

import { AdminSidebar } from '@/components/layout/AdminSidebar'
import { AppShell } from '@/shared/layouts/AppShell'

export function AdminLayout() {
  return (
    <AppShell
      headerTitle="Admin dashboard"
      sidebarWidthClass="w-64"
      renderSidebar={({ onNavigate }) => <AdminSidebar onNavigate={onNavigate} />}
    >
      <Outlet />
    </AppShell>
  )
}
