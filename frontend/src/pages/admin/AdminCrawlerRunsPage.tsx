import { useState } from 'react'

import { CrawlerAdminRunsSection } from '@/components/admin/crawler-admin-sections'
import { CrawlerAdminSubNav } from '@/components/admin/crawler-admin-subnav'

export function AdminCrawlerRunsPage() {
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold text-foreground">Crawl runs</h2>
        <p className="mt-1 text-sm text-muted-foreground">Monitor and cancel in-flight crawl jobs.</p>
      </div>
      <CrawlerAdminSubNav />
      {(msg || err) && (
        <div className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm">
          {err ? <p className="text-destructive">{err}</p> : null}
          {msg && !err ? <p>{msg}</p> : null}
        </div>
      )}
      <CrawlerAdminRunsSection
        onMessage={(m, e) => {
          setErr(e)
          setMsg(e ? null : m)
        }}
      />
    </div>
  )
}
