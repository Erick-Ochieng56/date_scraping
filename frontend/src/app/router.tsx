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
  CrawlerDiscoverPage,
  CrawlerDomainsPage,
  CrawlerHomePage,
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
      { path: 'targets', element: <TargetsPage /> },
      { path: 'targets/:targetId', element: <TargetFormPage /> },
      { path: 'runs', element: <RunsPage /> },
      { path: 'runs/:runId', element: <RunDetailPage /> },
      { path: 'crawler', element: <CrawlerHomePage /> },
      { path: 'crawler/discover', element: <CrawlerDiscoverPage /> },
      { path: 'crawler/domains', element: <CrawlerDomainsPage /> },
      { path: 'crawler/runs', element: <CrawlerRunsPage /> },
      { path: 'crawler/runs/:runId', element: <CrawlerRunDetailPage /> },
      { path: 'crawler/ai-search', element: <AiSearchPage variant="staff" /> },
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
      { path: 'scraper/targets', element: <AdminScraperTargetsPage /> },
      { path: 'scraper/runs', element: <AdminScraperRunsPage /> },
      { path: 'scraper', element: <AdminScraperOpsPage /> },
      { path: 'crawler/sources', element: <AdminCrawlerSourcesPage /> },
      { path: 'crawler/domains', element: <AdminCrawlerDomainsPage /> },
      { path: 'crawler/runs', element: <AdminCrawlerRunsPage /> },
      { path: 'crawler', element: <AdminCrawlerOpsPage /> },
      { path: 'ai-search', element: <AiSearchPage variant="admin" /> },
      { path: 'pipeline', element: <AdminPipelinePage /> },
      { path: 'monitoring', element: <AdminMonitoringPage /> },
      { path: 'audit', element: <AdminAuditPage /> },
      { path: 'settings', element: <AdminSettingsPage /> },
      { path: '*', element: <Navigate to="/admin" replace /> },
    ],
  },
])
