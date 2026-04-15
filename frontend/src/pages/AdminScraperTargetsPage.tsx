import { useState } from 'react'

import { ScraperAdminTargetsSection } from '@/components/admin/scraper-admin-sections'
import { ScraperAdminSubNav } from '@/components/admin/scraper-admin-subnav'

export function AdminScraperTargetsPage() {
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold text-foreground">Scrape targets</h2>
        <p className="mt-1 text-sm text-muted-foreground">Trigger scrapes for any configured target.</p>
      </div>
      <ScraperAdminSubNav />
      {(msg || err) && (
        <div className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm">
          {err ? <p className="text-destructive">{err}</p> : null}
          {msg && !err ? <p>{msg}</p> : null}
        </div>
      )}
      <ScraperAdminTargetsSection
        onMessage={(m, e) => {
          setErr(e)
          setMsg(e ? null : m)
        }}
      />
    </div>
  )
}
