import { Link } from 'react-router-dom'
import { useState } from 'react'

import {
  CrawlerAdminDomainsSection,
  CrawlerAdminRunsSection,
  CrawlerAdminSourcesSection,
  CrawlerAdminStatsCards,
} from '@/components/admin/crawler-admin-sections'
import { CrawlerAdminSubNav } from '@/components/admin/crawler-admin-subnav'

export function AdminCrawlerOpsPage() {
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  const onMessage = (m: string | null, e: string | null) => {
    setErr(e)
    setMsg(e ? null : m)
  }

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold text-foreground">Crawler</h2>
        <p className="mt-1 text-sm text-muted-foreground">
          Global crawl sources, domain queue, and run orchestration. Use buyer-intent AI search queries for best
          discovery results.
        </p>
      </div>

      <CrawlerAdminSubNav />

      {(msg || err) && (
        <div className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm">
          {err ? <p className="text-destructive">{err}</p> : null}
          {msg && !err ? <p>{msg}</p> : null}
        </div>
      )}

      <CrawlerAdminStatsCards />
      <CrawlerAdminSourcesSection onMessage={onMessage} />
      <CrawlerAdminDomainsSection onMessage={onMessage} />
      <CrawlerAdminRunsSection onMessage={onMessage} />

      <div className="flex flex-wrap gap-2">
        <Link
          to="/admin/ai-search"
          className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium hover:bg-muted"
        >
          AI search (Gemini)
        </Link>
        <Link
          to="/crawler/discover"
          className="inline-flex h-9 items-center rounded-md border border-border bg-background px-3 text-sm font-medium hover:bg-muted"
        >
          Staff discover UI
        </Link>
      </div>
    </div>
  )
}
