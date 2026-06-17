import { useState } from 'react'

import { AdminCrawlerRunsTable } from '@/features/admin/crawler/AdminCrawlerRunsTable'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { PageHeader } from '@/shared/components/PageHeader'

export function AdminCrawlerRunsPage() {
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  return (
    <div className="space-y-4">
      <PageHeader title="Crawl runs" description="Monitor and cancel in-flight crawl jobs globally." />
      <AlertBanner message={banner.message} error={banner.error} />
      <AdminCrawlerRunsTable onMessage={(m, e) => setBanner(e ? { error: e } : m ? { message: m } : {})} />
    </div>
  )
}
