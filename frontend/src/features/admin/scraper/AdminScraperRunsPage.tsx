import { useState } from 'react'

import { AdminScraperRunsTable } from '@/features/admin/scraper/AdminScraperRunsTable'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { PageHeader } from '@/shared/components/PageHeader'

export function AdminScraperRunsPage() {
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  return (
    <div className="space-y-4">
      <PageHeader
        title="Scrape runs"
        description="Inspect outcomes and retry failed runs globally."
      />
      <AlertBanner message={banner.message} error={banner.error} />
      <AdminScraperRunsTable onMessage={(m, e) => setBanner(e ? { error: e } : m ? { message: m } : {})} />
    </div>
  )
}
