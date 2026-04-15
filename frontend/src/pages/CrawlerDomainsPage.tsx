import { useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'

import { Button } from '@/components/ui/button'
import { listCrawlDomains, triggerCrawlDomain } from '@/lib/api/dashboard'

export function CrawlerDomainsPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [crawlStatus, setCrawlStatus] = useState('')

  const domainsQ = useQuery({
    queryKey: ['crawl-domains', search, crawlStatus],
    queryFn: () =>
      listCrawlDomains({ page_size: 50, search: search || undefined, crawl_status: crawlStatus || undefined }),
  })

  const triggerM = useMutation({
    mutationFn: (domainId: number) => triggerCrawlDomain(domainId),
    onSuccess: () => void qc.invalidateQueries({ queryKey: ['crawl-domains'] }),
  })

  return (
    <div className="space-y-4">
      <h2 className="text-2xl font-semibold text-foreground">Domain queue</h2>
      <div className="flex flex-wrap gap-2">
        <input
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          placeholder="Search domain..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <select
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          value={crawlStatus}
          onChange={(e) => setCrawlStatus(e.target.value)}
        >
          <option value="">All statuses</option>
          <option value="pending">Pending</option>
          <option value="crawling">Crawling</option>
          <option value="completed">Completed</option>
          <option value="failed">Failed</option>
        </select>
      </div>
      <div className="overflow-auto rounded-lg border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-3 py-2 text-left">Domain</th>
              <th className="px-3 py-2 text-left">Discovery URL</th>
              <th className="px-3 py-2 text-left">Source</th>
              <th className="px-3 py-2 text-left">Status</th>
              <th className="px-3 py-2 text-left">Attempts</th>
              <th className="px-3 py-2 text-left">Action</th>
            </tr>
          </thead>
          <tbody>
            {(domainsQ.data?.items ?? []).map((d) => (
              <tr key={d.id} className="border-t border-border">
                <td className="px-3 py-2">{d.domain}</td>
                <td className="max-w-xs truncate px-3 py-2 text-xs text-muted-foreground">
                  {d.source_url ? (
                    <a className="text-primary underline-offset-2 hover:underline" href={d.source_url} target="_blank" rel="noreferrer">
                      {d.source_url}
                    </a>
                  ) : (
                    '—'
                  )}
                </td>
                <td className="px-3 py-2">{d.source_name || '-'}</td>
                <td className="px-3 py-2">{d.crawl_status}</td>
                <td className="px-3 py-2">{d.crawl_attempts}</td>
                <td className="px-3 py-2">
                  <Button size="sm" disabled={triggerM.isPending} onClick={() => triggerM.mutate(d.id)}>
                    Crawl now
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

