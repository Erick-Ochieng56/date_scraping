import { Outlet } from 'react-router-dom'

import { AdminSidebar } from '@/components/layout/AdminSidebar'
import { AppShell } from '@/shared/layouts/AppShell'

export function AdminLayout() {
  return (
    <AppShell
      headerTitle="Ateric Leads — Admin"
      sidebarWidthClass="w-64"
      renderSidebar={({ onNavigate }) => <AdminSidebar onNavigate={onNavigate} />}
    >
      <Outlet />
    </AppShell>
  )
}
