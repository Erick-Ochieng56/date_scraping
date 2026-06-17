import { useState } from 'react'

import { AdminCrawlerDomainsTable } from '@/features/admin/crawler/AdminCrawlerDomainsTable'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { PageHeader } from '@/shared/components/PageHeader'

export function AdminCrawlerDomainsPage() {
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  return (
    <div className="space-y-4">
      <PageHeader
        title="Domain queue"
        description="Pending and completed crawl targets across all users."
      />
      <AlertBanner message={banner.message} error={banner.error} />
      <AdminCrawlerDomainsTable onMessage={(m, e) => setBanner(e ? { error: e } : m ? { message: m } : {})} />
    </div>
  )
}
