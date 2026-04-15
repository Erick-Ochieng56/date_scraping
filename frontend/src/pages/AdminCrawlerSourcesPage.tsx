import { useState } from 'react'

import { CrawlerAdminSourcesSection } from '@/components/admin/crawler-admin-sections'
import { CrawlerAdminSubNav } from '@/components/admin/crawler-admin-subnav'

export function AdminCrawlerSourcesPage() {
  const [msg, setMsg] = useState<string | null>(null)
  const [err, setErr] = useState<string | null>(null)

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold text-foreground">Crawl sources</h2>
        <p className="mt-1 text-sm text-muted-foreground">Enable or disable discovery sources globally.</p>
      </div>
      <CrawlerAdminSubNav />
      {(msg || err) && (
        <div className="rounded-lg border border-border bg-muted/40 px-3 py-2 text-sm">
          {err ? <p className="text-destructive">{err}</p> : null}
          {msg && !err ? <p>{msg}</p> : null}
        </div>
      )}
      <CrawlerAdminSourcesSection
        onMessage={(m, e) => {
          setErr(e)
          setMsg(e ? null : m)
        }}
      />
    </div>
  )
}
