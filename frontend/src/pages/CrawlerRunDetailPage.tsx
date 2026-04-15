import { useState } from 'react'
import { useQuery } from '@tanstack/react-query'
import { useParams } from 'react-router-dom'

import { getCrawlRun, listCrawlRunDomainResults } from '@/lib/api/dashboard'

export function CrawlerRunDetailPage() {
  const params = useParams()
  const runId = Number(params.runId)
  const [state, setState] = useState('')
  const [errorsOnly, setErrorsOnly] = useState(false)

  const runQ = useQuery({
    queryKey: ['crawler-run', runId],
    queryFn: () => getCrawlRun(runId),
    enabled: Number.isFinite(runId) && runId > 0,
    refetchInterval: (q) => (q.state.data?.status === 'running' ? 5000 : false),
  })
  const domainsQ = useQuery({
    queryKey: ['crawler-run-domains', runId, state, errorsOnly],
    queryFn: () =>
      listCrawlRunDomainResults(runId, {
        page_size: 100,
        state: state || undefined,
        errors_only: errorsOnly || undefined,
      }),
    enabled: Number.isFinite(runId) && runId > 0,
    refetchInterval: runQ.data?.status === 'running' ? 5000 : false,
  })

  if (!runId) return <p>Invalid run id.</p>

  return (
    <div className="space-y-4">
      <div>
        <h2 className="text-2xl font-semibold text-foreground">Crawler run #{runId}</h2>
        <p className="text-sm text-muted-foreground">
          {runQ.data?.status_display ?? runQ.data?.status ?? 'Loading status...'}
        </p>
      </div>

      <div className="grid gap-3 md:grid-cols-4">
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Domains</p>
          <p className="text-lg font-semibold">{runQ.data?.summary?.total_domains ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Errors</p>
          <p className="text-lg font-semibold">{runQ.data?.summary?.failed_domains ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Prospects created</p>
          <p className="text-lg font-semibold">{runQ.data?.summary?.prospects_created ?? 0}</p>
        </div>
        <div className="rounded-lg border border-border p-4">
          <p className="text-sm text-muted-foreground">Prospects updated</p>
          <p className="text-lg font-semibold">{runQ.data?.summary?.prospects_updated ?? 0}</p>
        </div>
      </div>

      <div className="flex flex-wrap gap-2">
        <select
          className="h-9 rounded-md border border-border bg-background px-3 text-sm"
          value={state}
          onChange={(e) => setState(e.target.value)}
        >
          <option value="">All states</option>
          <option value="queued">Queued</option>
          <option value="crawled">Crawled</option>
          <option value="analyzed">Analyzed</option>
          <option value="scored">Scored</option>
          <option value="failed">Failed</option>
        </select>
        <label className="inline-flex items-center gap-2 rounded-md border border-border px-3 text-sm">
          <input type="checkbox" checked={errorsOnly} onChange={(e) => setErrorsOnly(e.target.checked)} />
          Errors only
        </label>
      </div>

      <div className="overflow-auto rounded-lg border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-3 py-2 text-left">Domain</th>
              <th className="px-3 py-2 text-left">State</th>
              <th className="px-3 py-2 text-left">Score</th>
              <th className="px-3 py-2 text-left">Prospect</th>
              <th className="px-3 py-2 text-left">Error</th>
            </tr>
          </thead>
          <tbody>
            {(domainsQ.data?.items ?? []).map((row) => (
              <tr key={row.id} className="border-t border-border align-top">
                <td className="px-3 py-2">{row.domain_name}</td>
                <td className="px-3 py-2">{row.state}</td>
                <td className="px-3 py-2">
                  {row.score} {row.score_label ? `(${row.score_label})` : ''}
                </td>
                <td className="px-3 py-2">
                  {row.prospect_created ? 'Created' : row.prospect_updated ? 'Updated' : '-'}
                </td>
                <td className="px-3 py-2 text-destructive">{row.crawl_error || '-'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}

