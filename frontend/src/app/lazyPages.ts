import { lazy, type ComponentType, type LazyExoticComponent } from 'react'

function lazyNamed(
  load: () => Promise<Record<string, ComponentType<unknown>>>,
  exportKey: string,
) {
  return lazy(async () => {
    const mod = await load()
    const Named = mod[exportKey]
    if (!Named) {
      throw new Error(`lazyPages: missing export "${exportKey}"`)
    }
    return { default: Named }
  })
}

export const AdminAuditPage = lazyNamed(() => import('@/pages/admin/AdminAuditPage'), 'AdminAuditPage')
export const AdminCrawlerDomainsPage = lazyNamed(
  () => import('@/pages/admin/AdminCrawlerDomainsPage'),
  'AdminCrawlerDomainsPage',
)
export const AdminCrawlerOpsPage = lazyNamed(() => import('@/pages/admin/AdminCrawlerOpsPage'), 'AdminCrawlerOpsPage')
export const CrawlerAdminLayout = lazyNamed(
  () => import('@/features/admin/crawler/CrawlerAdminLayout'),
  'CrawlerAdminLayout',
)
export const AdminCrawlerRunsPage = lazyNamed(() => import('@/pages/admin/AdminCrawlerRunsPage'), 'AdminCrawlerRunsPage')
export const AdminCrawlerSourcesPage = lazyNamed(
  () => import('@/pages/admin/AdminCrawlerSourcesPage'),
  'AdminCrawlerSourcesPage',
)
export const AdminHomePage = lazyNamed(() => import('@/pages/admin/AdminHomePage'), 'AdminHomePage')
export const AdminMonitoringPage = lazyNamed(() => import('@/pages/admin/AdminMonitoringPage'), 'AdminMonitoringPage')
export const AdminPipelinePage = lazyNamed(() => import('@/pages/admin/AdminPipelinePage'), 'AdminPipelinePage')
export const AdminQualityPage = lazyNamed(() => import('@/pages/admin/AdminQualityPage'), 'AdminQualityPage')
export const AdminScraperOpsPage = lazyNamed(() => import('@/pages/admin/AdminScraperOpsPage'), 'AdminScraperOpsPage')
export const ScraperAdminLayout = lazyNamed(
  () => import('@/features/admin/scraper/ScraperAdminLayout'),
  'ScraperAdminLayout',
)
export const AdminScraperRunsPage = lazyNamed(() => import('@/pages/admin/AdminScraperRunsPage'), 'AdminScraperRunsPage')
export const AdminScraperTargetsPage = lazyNamed(
  () => import('@/pages/admin/AdminScraperTargetsPage'),
  'AdminScraperTargetsPage',
)
export const AdminSettingsPage = lazyNamed(() => import('@/pages/admin/AdminSettingsPage'), 'AdminSettingsPage')
export const AdminProfilePage = lazyNamed(() => import('@/pages/admin/AdminProfilePage'), 'AdminProfilePage')
export const AdminUsersPage = lazyNamed(() => import('@/pages/admin/AdminUsersPage'), 'AdminUsersPage')
type AiSearchVariant = 'staff' | 'admin'

export const AiSearchPage: LazyExoticComponent<ComponentType<{ variant: AiSearchVariant }>> = lazy(
  async () => {
    const { AiSearchPage: Page } = await import('@/pages/staff/AiSearchPage')
    return { default: Page }
  },
)
export const CrawlerLayout = lazyNamed(() => import('@/features/crawler/CrawlerLayout'), 'CrawlerLayout')
export const CrawlerDiscoverPage = lazyNamed(() => import('@/pages/staff/CrawlerDiscoverPage'), 'CrawlerDiscoverPage')
export const CrawlerDomainsPage = lazyNamed(() => import('@/pages/staff/CrawlerDomainsPage'), 'CrawlerDomainsPage')
export const CrawlerHomePage = lazyNamed(() => import('@/pages/staff/CrawlerHomePage'), 'CrawlerHomePage')
export const CrawlerRunDetailPage = lazyNamed(() => import('@/pages/staff/CrawlerRunDetailPage'), 'CrawlerRunDetailPage')
export const CrawlerRunsPage = lazyNamed(() => import('@/pages/staff/CrawlerRunsPage'), 'CrawlerRunsPage')
export const CrawlSchedulesPage = lazyNamed(() => import('@/pages/staff/CrawlSchedulesPage'), 'CrawlSchedulesPage')
export const EventProspectsPage = lazyNamed(() => import('@/pages/staff/EventProspectsPage'), 'EventProspectsPage')
export const HomePage = lazyNamed(() => import('@/pages/HomePage'), 'HomePage')
export const LeadCreatePage = lazyNamed(() => import('@/pages/staff/LeadCreatePage'), 'LeadCreatePage')
export const LeadDetailPage = lazyNamed(() => import('@/pages/staff/LeadDetailPage'), 'LeadDetailPage')
export const LeadsPage = lazyNamed(() => import('@/pages/staff/LeadsPage'), 'LeadsPage')
export const LoginPage = lazyNamed(() => import('@/pages/LoginPage'), 'LoginPage')
export const NotificationsPage = lazyNamed(
  () => import('@/pages/staff/NotificationsPage'),
  'NotificationsPage'
)
export const ProfilePage = lazyNamed(() => import('@/pages/staff/ProfilePage'), 'ProfilePage')
export const ProspectCreatePage = lazyNamed(() => import('@/pages/staff/ProspectCreatePage'), 'ProspectCreatePage')
export const ProspectDetailPage = lazyNamed(() => import('@/pages/staff/ProspectDetailPage'), 'ProspectDetailPage')
export const ProspectsPage = lazyNamed(() => import('@/pages/staff/ProspectsPage'), 'ProspectsPage')
export const RunDetailPage = lazyNamed(() => import('@/pages/staff/RunDetailPage'), 'RunDetailPage')
export const RunsPage = lazyNamed(() => import('@/pages/staff/RunsPage'), 'RunsPage')
export const TargetFormPage = lazyNamed(() => import('@/pages/staff/TargetFormPage'), 'TargetFormPage')
export const TargetsPage = lazyNamed(() => import('@/pages/staff/TargetsPage'), 'TargetsPage')
