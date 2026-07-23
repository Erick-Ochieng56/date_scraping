import { Suspense } from 'react'
import { createBrowserRouter, Navigate } from 'react-router-dom'

import {
  AdminAuditPage,
  AdminCrawlerDomainsPage,
  AdminCrawlerOpsPage,
  AdminCrawlerRunsPage,
  AdminCrawlerSourcesPage,
  AdminHomePage,
  AdminMonitoringPage,
  AdminPipelinePage,
  AdminScraperOpsPage,
  AdminScraperRunsPage,
  AdminScraperTargetsPage,
  AdminSettingsPage,
  AdminUsersPage,
  AiSearchPage,
  CrawlerAdminLayout,
  CrawlerDiscoverPage,
  CrawlerDomainsPage,
  CrawlerLayout,
  CrawlerRunDetailPage,
  CrawlerRunsPage,
  HomePage,
  LeadDetailPage,
  LeadsPage,
  LoginPage,
  ProspectDetailPage,
  ProspectsPage,
  RunDetailPage,
  RunsPage,
  ScraperAdminLayout,
  TargetFormPage,
  TargetsPage,
} from '@/app/lazyPages'
import { LoginLoadingFallback } from '@/components/LoginLoadingFallback'
import { ProtectedRoute } from '@/components/ProtectedRoute'
import { RouteErrorPage } from '@/components/RouteErrorPage'
import { AdminLayout } from '@/components/layout/AdminLayout'
import { DashboardLayout } from '@/components/layout/DashboardLayout'

export const router = createBrowserRouter([
  {
    path: '/login',
    element: (
      <Suspense fallback={<LoginLoadingFallback />}>
        <LoginPage />
      </Suspense>
    ),
    errorElement: <RouteErrorPage />,
  },
  {
    path: '/',
    element: (
      <ProtectedRoute allowRoles={['staff']}>
        <DashboardLayout />
      </ProtectedRoute>
    ),
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, element: <HomePage /> },
      { path: 'find-leads', element: <AiSearchPage variant="staff" /> },
      { path: 'targets', element: <TargetsPage /> },
      { path: 'targets/wizard', element: <Navigate to="/targets/new" replace /> },
      { path: 'targets/:targetId', element: <TargetFormPage /> },
      { path: 'runs', element: <RunsPage /> },
      { path: 'runs/:runId', element: <RunDetailPage /> },
      {
        path: 'crawler',
        element: <CrawlerLayout />,
        children: [
          // The Overview page was removed — Discover is the crawler's front door.
          { index: true, element: <Navigate to="/crawler/discover" replace /> },
          { path: 'discover', element: <CrawlerDiscoverPage /> },
          { path: 'domains', element: <CrawlerDomainsPage /> },
          { path: 'runs', element: <CrawlerRunsPage /> },
          { path: 'runs/:runId', element: <CrawlerRunDetailPage /> },
          // Moved to the top-level /find-leads hub (Phase 3) — kept as a redirect
          // so old bookmarks/links still resolve.
          { path: 'ai-search', element: <Navigate to="/find-leads" replace /> },
        ],
      },
      { path: 'prospects', element: <ProspectsPage /> },
      { path: 'prospects/:prospectId', element: <ProspectDetailPage /> },
      { path: 'leads', element: <LeadsPage /> },
      { path: 'leads/:leadId', element: <LeadDetailPage /> },
      { path: '*', element: <Navigate to="/" replace /> },
    ],
  },
  {
    path: '/admin',
    element: (
      <ProtectedRoute allowRoles={['admin']}>
        <AdminLayout />
      </ProtectedRoute>
    ),
    errorElement: <RouteErrorPage />,
    children: [
      { index: true, element: <AdminHomePage /> },
      { path: 'users', element: <AdminUsersPage /> },
      {
        path: 'scraper',
        element: <ScraperAdminLayout />,
        children: [
          { index: true, element: <AdminScraperOpsPage /> },
          { path: 'targets', element: <AdminScraperTargetsPage /> },
          { path: 'runs', element: <AdminScraperRunsPage /> },
        ],
      },
      {
        path: 'crawler',
        element: <CrawlerAdminLayout />,
        children: [
          { index: true, element: <AdminCrawlerOpsPage /> },
          { path: 'sources', element: <AdminCrawlerSourcesPage /> },
          { path: 'domains', element: <AdminCrawlerDomainsPage /> },
          { path: 'runs', element: <AdminCrawlerRunsPage /> },
        ],
      },
      { path: 'ai-search', element: <AiSearchPage variant="admin" /> },
      { path: 'pipeline', element: <AdminPipelinePage /> },
      { path: 'monitoring', element: <AdminMonitoringPage /> },
      { path: 'audit', element: <AdminAuditPage /> },
      { path: 'settings', element: <AdminSettingsPage /> },
      { path: '*', element: <Navigate to="/admin" replace /> },
    ],
  },
])
