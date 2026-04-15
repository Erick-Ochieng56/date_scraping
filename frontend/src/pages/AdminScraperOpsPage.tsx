import { Link } from 'react-router-dom'
import { useState } from 'react'

import { ScraperAdminRunsSection, ScraperAdminStatsCards, ScraperAdminTargetsSection } from '@/components/admin/scraper-admin-sections'
import { ScraperAdminSubNav } from '@/components/admin/scraper-admin-subnav'

export function AdminScraperOpsPage() {
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const onMessage = (m: string | null, e: string | null) => {
    setErr(e)
    setMsg(e ? null : m)
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold text-foreground">Scraper</h2>
        <p className="mt-1 text-sm text-muted-foreground">Global scraper targets and run history.</p>
      </div>

      <ScraperAdminSubNav />

      {(msg || err) && (
        <div className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm">
          {err ? <p className="text-destructive">{err}</p> : null}
          {msg && !err ? <p>{msg}</p> : null}
        </div>
      )}

      <ScraperAdminStatsCards />
      <ScraperAdminTargetsSection onMessage={onMessage} />
      <ScraperAdminRunsSection onMessage={onMessage} />

      <div className="flex flex-wrap gap-2">
        <Link
          to="/targets"
          className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium hover:bg-muted"
        >
          Staff targets UI
        </Link>
        <Link
          to="/runs"
          className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium hover:bg-muted"
        >
          Staff runs UI
        </Link>
      </div>
    </div>
  )
}
