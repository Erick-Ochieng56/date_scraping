import { useState } from 'react'

import { AdminCrawlerSourcesTable } from '@/features/admin/crawler/AdminCrawlerSourcesTable'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { PageHeader } from '@/shared/components/PageHeader'

export function AdminCrawlerSourcesPage() {
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  return (
    <div className="space-y-4">
      <PageHeader title="Crawl sources" description="Enable or disable discovery sources globally." />
      <AlertBanner message={banner.message} error={banner.error} />
      <AdminCrawlerSourcesTable onMessage={(m, e) => setBanner(e ? { error: e } : m ? { message: m } : {})} />
    </div>
  )
}
