import { useState } from 'react'

import { AdminScraperTargetsTable } from '@/features/admin/scraper/AdminScraperTargetsTable'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { PageHeader } from '@/shared/components/PageHeader'

export function AdminScraperTargetsPage() {
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})

  return (
    <div className="space-y-4">
      <PageHeader
        title="Scrape targets"
        description="Trigger scrapes for any configured target across all users."
      />
      <AlertBanner message={banner.message} error={banner.error} />
      <AdminScraperTargetsTable
        onMessage={(m, e) => setBanner(e ? { error: e } : m ? { message: m } : {})}
      />
    </div>
  )
}
