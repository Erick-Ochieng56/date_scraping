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

export const AdminAuditPage = lazyNamed(() => import('@/pages/AdminAuditPage'), 'AdminAuditPage')
export const AdminCrawlerDomainsPage = lazyNamed(
  () => import('@/pages/AdminCrawlerDomainsPage'),
  'AdminCrawlerDomainsPage',
)
export const AdminCrawlerOpsPage = lazyNamed(() => import('@/pages/AdminCrawlerOpsPage'), 'AdminCrawlerOpsPage')
export const AdminCrawlerRunsPage = lazyNamed(() => import('@/pages/AdminCrawlerRunsPage'), 'AdminCrawlerRunsPage')
export const AdminCrawlerSourcesPage = lazyNamed(
  () => import('@/pages/AdminCrawlerSourcesPage'),
  'AdminCrawlerSourcesPage',
)
export const AdminHomePage = lazyNamed(() => import('@/pages/AdminHomePage'), 'AdminHomePage')
export const AdminMonitoringPage = lazyNamed(() => import('@/pages/AdminMonitoringPage'), 'AdminMonitoringPage')
export const AdminPipelinePage = lazyNamed(() => import('@/pages/AdminPipelinePage'), 'AdminPipelinePage')
export const AdminScraperOpsPage = lazyNamed(() => import('@/pages/AdminScraperOpsPage'), 'AdminScraperOpsPage')
export const AdminScraperRunsPage = lazyNamed(() => import('@/pages/AdminScraperRunsPage'), 'AdminScraperRunsPage')
export const AdminScraperTargetsPage = lazyNamed(
  () => import('@/pages/AdminScraperTargetsPage'),
  'AdminScraperTargetsPage',
)
export const AdminSettingsPage = lazyNamed(() => import('@/pages/AdminSettingsPage'), 'AdminSettingsPage')
export const AdminUsersPage = lazyNamed(() => import('@/pages/AdminUsersPage'), 'AdminUsersPage')
type AiSearchVariant = 'staff' | 'admin'

export const AiSearchPage: LazyExoticComponent<ComponentType<{ variant: AiSearchVariant }>> = lazy(
  async () => {
    const { AiSearchPage: Page } = await import('@/pages/AiSearchPage')
    return { default: Page }
  },
)
export const CrawlerDiscoverPage = lazyNamed(() => import('@/pages/CrawlerDiscoverPage'), 'CrawlerDiscoverPage')
export const CrawlerDomainsPage = lazyNamed(() => import('@/pages/CrawlerDomainsPage'), 'CrawlerDomainsPage')
export const CrawlerHomePage = lazyNamed(() => import('@/pages/CrawlerHomePage'), 'CrawlerHomePage')
export const CrawlerRunDetailPage = lazyNamed(() => import('@/pages/CrawlerRunDetailPage'), 'CrawlerRunDetailPage')
export const CrawlerRunsPage = lazyNamed(() => import('@/pages/CrawlerRunsPage'), 'CrawlerRunsPage')
export const HomePage = lazyNamed(() => import('@/pages/HomePage'), 'HomePage')
export const LeadDetailPage = lazyNamed(() => import('@/pages/LeadDetailPage'), 'LeadDetailPage')
export const LeadsPage = lazyNamed(() => import('@/pages/LeadsPage'), 'LeadsPage')
export const LoginPage = lazyNamed(() => import('@/pages/LoginPage'), 'LoginPage')
export const ProspectDetailPage = lazyNamed(() => import('@/pages/ProspectDetailPage'), 'ProspectDetailPage')
export const ProspectsPage = lazyNamed(() => import('@/pages/ProspectsPage'), 'ProspectsPage')
export const RunDetailPage = lazyNamed(() => import('@/pages/RunDetailPage'), 'RunDetailPage')
export const RunsPage = lazyNamed(() => import('@/pages/RunsPage'), 'RunsPage')
export const TargetFormPage = lazyNamed(() => import('@/pages/TargetFormPage'), 'TargetFormPage')
export const TargetsPage = lazyNamed(() => import('@/pages/TargetsPage'), 'TargetsPage')
