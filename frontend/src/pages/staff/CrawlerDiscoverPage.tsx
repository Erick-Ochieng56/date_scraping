import { useMemo, useState } from 'react'
import { useMutation, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'
import { ArrowLeft, Copy, ExternalLink, Plus, Search, Trash2 } from 'lucide-react'

import { Button } from '@/components/ui/button'
import { crawlerPreview, crawlerQueue, type CrawlerDiscoveryHit } from '@/lib/api/dashboard'

const EXAMPLE_QUERIES = [
  'translation conference Europe',
  'NGO language services Africa',
  'international association annual meeting',
]

const MAX_OPTIONS = [10, 20, 30, 50] as const

type PreviewRow = {
  /** Stable row id (landing URL preferred). */
  id: string
  domain: string
  landing: string
}

function normalizeDiscoveryEntry(raw: string): string {
  const value = raw.trim()
  if (!value) return ''
  const candidate = /^https?:\/\//i.test(value) ? value : `https://${value}`
  try {
    const u = new URL(candidate)
    if (!u.hostname) return ''
    const path = u.pathname || ''
    const hasPath = path.length > 1
    const hasQuery = (u.search || '').length > 1
    if (hasPath || hasQuery) {
      let out = `${u.origin}${path}${u.search || ''}`
      if (out.endsWith('/') && path !== '/' && path.length > 1) {
        out = out.replace(/\/+$/, '')
      }
      return out
    }
    return `${u.origin}`
  } catch {
    return ''
  }
}

function hitsToRows(hits: CrawlerDiscoveryHit[]): PreviewRow[] {
  return hits.map((h, i) => {
    const landing = (h.source_url || h.domain || '').trim()
    let domain = (h.domain || '').trim()
    if (!domain && landing) {
      try {
        domain = new URL(landing).origin
      } catch {
        domain = landing
      }
    }
    return {
      id: landing || `${domain}-${i}`,
      domain,
      landing,
    }
  })
}

function urlsToRows(urls: string[]): PreviewRow[] {
  return urls.map((u, i) => {
    const landing = u.trim()
    let domain = landing
    try {
      domain = new URL(landing).origin
    } catch {
      /* keep */
    }
    return { id: landing || `row-${i}`, domain, landing }
  })
}

export function CrawlerDiscoverPage() {
  const qc = useQueryClient()
  const [query, setQuery] = useState('')
  const [maxResults, setMaxResults] = useState<number>(20)
  const [manualUrl, setManualUrl] = useState('')
  const [previewRows, setPreviewRows] = useState<PreviewRow[]>([])
  const [selected, setSelected] = useState<Set<string>>(() => new Set())
  const [banner, setBanner] = useState<{ type: 'ok' | 'err'; text: string } | null>(null)
  const [lastQueue, setLastQueue] = useState<{
    queued: number
    new_domains: number
    run_id: number | null
  } | null>(null)

  const selectedLandings = useMemo(
    () => previewRows.filter((r) => selected.has(r.id)).map((r) => r.landing),
    [previewRows, selected]
  )

  const invalidateCrawler = () => {
    void qc.invalidateQueries({ queryKey: ['crawl-sources-home'] })
    void qc.invalidateQueries({ queryKey: ['crawl-domains-home'] })
    void qc.invalidateQueries({ queryKey: ['crawl-domains'] })
    void qc.invalidateQueries({ queryKey: ['crawl-runs-home'] })
    void qc.invalidateQueries({ queryKey: ['crawler-runs-page'] })
    void qc.invalidateQueries({ queryKey: ['crawl-domain-count'] })
    void qc.invalidateQueries({ queryKey: ['crawl-run-count'] })
  }

  const previewM = useMutation({
    mutationFn: () => crawlerPreview(query.trim(), maxResults),
    onMutate: () => {
      setBanner(null)
      setLastQueue(null)
    },
    onSuccess: (data) => {
      const rows =
        data.hits && data.hits.length > 0 ? hitsToRows(data.hits) : urlsToRows(data.urls ?? [])
      setPreviewRows(rows)
      setSelected(new Set(rows.map((r) => r.id)))
      if (rows.length === 0) {
        setBanner({
          type: 'ok',
          text: 'No URLs returned — try a different phrase or check Serper/Bing configuration on the server.',
        })
      }
    },
    onError: (err: unknown) => {
      const ax = err as { response?: { data?: { error?: string } } }
      setBanner({ type: 'err', text: ax.response?.data?.error ?? 'Preview failed. Try again.' })
    },
  })

  const queueM = useMutation({
    mutationFn: (withCrawl: boolean) =>
      crawlerQueue({
        query: query.trim(),
        max_results: maxResults,
        auto_crawl: withCrawl,
        urls: selectedLandings,
      }),
    onMutate: () => setBanner(null),
    onSuccess: (data, withCrawl) => {
      setLastQueue({
        queued: data.queued,
        new_domains: data.new_domains,
        run_id: data.run_id ?? null,
      })
      const crawlNote = withCrawl
        ? data.run_id != null
          ? ` Crawl run #${data.run_id} started.`
          : ' Nothing was due for immediate crawl (domains may already be queued).'
        : ' Domains are pending — start crawls from the domain queue or crawler home.'
      setBanner({
        type: 'ok',
        text: `Queued ${data.queued} domain(s), ${data.new_domains} new.${crawlNote}`,
      })
      invalidateCrawler()
    },
    onError: (err: unknown) => {
      const ax = err as { response?: { data?: { error?: string } } }
      setBanner({ type: 'err', text: ax.response?.data?.error ?? 'Queue failed.' })
    },
  })

  const canPreview = query.trim().length > 0
  const canQueue = query.trim().length > 0 && selectedLandings.length > 0

  const toggleRow = (id: string) => {
    setSelected((prev) => {
      const next = new Set(prev)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })
  }

  const selectAll = () => setSelected(new Set(previewRows.map((r) => r.id)))
  const selectNone = () => setSelected(new Set())

  const removeRow = (id: string) => {
    setPreviewRows((prev) => prev.filter((r) => r.id !== id))
    setSelected((prev) => {
      const next = new Set(prev)
      next.delete(id)
      return next
    })
  }

  const addManualRow = () => {
    const landing = normalizeDiscoveryEntry(manualUrl)
    if (!landing) {
      setBanner({ type: 'err', text: 'Enter a valid URL or domain (deep links are kept).' })
      return
    }
    if (previewRows.some((r) => r.landing === landing)) {
      setBanner({ type: 'ok', text: 'That URL is already in the preview list.' })
      return
    }
    let domain = landing
    try {
      domain = new URL(landing).origin
    } catch {
      /* */
    }
    const row: PreviewRow = { id: landing, domain, landing }
    setPreviewRows((prev) => [...prev, row])
    setSelected((prev) => new Set(prev).add(row.id))
    setManualUrl('')
    setBanner(null)
  }

  const clearPreview = () => {
    setPreviewRows([])
    setSelected(new Set())
    setLastQueue(null)
    setBanner(null)
  }

  const copyUrl = async (u: string) => {
    try {
      await navigator.clipboard.writeText(u)
      setBanner({ type: 'ok', text: 'Copied to clipboard.' })
    } catch {
      setBanner({ type: 'err', text: 'Could not copy.' })
    }
  }

  return (
    <div className="space-y-6">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Button variant="ghost" className="mb-2 -ml-2 h-8 gap-1 px-2 text-muted-foreground" asChild>
            <Link to="/crawler">
              <ArrowLeft className="size-4" aria-hidden />
              Crawler home
            </Link>
          </Button>
          <h2 className="text-2xl font-semibold text-foreground">Discover domains</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Search the open web for sites to add to <strong>your</strong> crawler queue. Serp results keep the{' '}
            <strong>landing page URL</strong> (e.g. <code className="rounded bg-muted px-1">/events/…</code>) so the
            crawler starts on that page, not only the homepage. Preview, trim the list, then enqueue or enqueue + crawl.
          </p>
        </div>
      </div>

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="text-sm font-medium text-foreground">How it works</h3>
        <ol className="mt-2 list-inside list-decimal space-y-1 text-sm text-muted-foreground">
          <li>Enter a short search phrase (what you would type into a search engine).</li>
          <li>
            Preview loads <strong>landing URLs</strong> from results — uncheck rows you do not want. You can paste a
            specific event or tender URL under the table.
          </li>
          <li>
            <strong>Add to queue</strong> saves domains as pending with that landing URL as <code>source_url</code>.{' '}
            <strong>Queue &amp; crawl</strong> also starts a crawl run for domains that are due.
          </li>
        </ol>
      </div>

      {banner ? (
        <div
          className={`rounded-lg border px-3 py-2 text-sm ${
            banner.type === 'err'
              ? 'border-destructive/40 bg-destructive/10 text-destructive'
              : 'border-border bg-muted/50 text-foreground'
          }`}
        >
          {banner.text}
        </div>
      ) : null}

      <div className="flex flex-col gap-4 rounded-lg border border-border bg-card p-4">
        <div className="flex flex-wrap items-end gap-3">
          <div className="min-w-[min(100%,280px)] flex-1">
            <label className="text-xs font-medium text-muted-foreground" htmlFor="discover-query">
              Search phrase
            </label>
            <input
              id="discover-query"
              className="mt-1 h-10 w-full rounded-md border border-border bg-background px-3 text-sm"
              placeholder='e.g. "translation events Kenya" or inurl:events site:.org …'
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && canPreview && !previewM.isPending) previewM.mutate()
              }}
            />
          </div>
          <div>
            <label className="text-xs font-medium text-muted-foreground" htmlFor="discover-max">
              Max results
            </label>
            <select
              id="discover-max"
              className="mt-1 h-10 rounded-md border border-border bg-background px-3 text-sm"
              value={maxResults}
              onChange={(e) => setMaxResults(Number(e.target.value))}
            >
              {MAX_OPTIONS.map((n) => (
                <option key={n} value={n}>
                  {n}
                </option>
              ))}
            </select>
          </div>
        </div>

        <div>
          <p className="text-xs font-medium text-muted-foreground">Try an example</p>
          <div className="mt-2 flex flex-wrap gap-2">
            {EXAMPLE_QUERIES.map((ex) => (
              <Button
                key={ex}
                type="button"
                size="sm"
                variant="outline"
                className="h-8 text-xs"
                onClick={() => {
                  setQuery(ex)
                  setLastQueue(null)
                }}
              >
                {ex}
              </Button>
            ))}
          </div>
        </div>

        <div className="flex flex-wrap gap-2 border-t border-border pt-4">
          <Button disabled={!canPreview || previewM.isPending} onClick={() => previewM.mutate()}>
            <Search className="mr-1.5 size-4" aria-hidden />
            {previewM.isPending ? 'Searching…' : 'Preview URLs'}
          </Button>
          <Button type="button" variant="outline" disabled={previewRows.length === 0} onClick={clearPreview}>
            Clear preview
          </Button>
          <Button type="button" variant="outline" disabled={previewRows.length === 0} onClick={selectAll}>
            Select all
          </Button>
          <Button type="button" variant="outline" disabled={previewRows.length === 0} onClick={selectNone}>
            Select none
          </Button>
        </div>

        <div className="flex flex-wrap gap-2">
          <Button
            variant="secondary"
            disabled={!canQueue || queueM.isPending}
            onClick={() => queueM.mutate(false)}
            title="Save domains to your queue without starting a crawl run"
          >
            {queueM.isPending ? 'Working…' : 'Add to queue only'}
          </Button>
          <Button
            disabled={!canQueue || queueM.isPending}
            onClick={() => queueM.mutate(true)}
            title="Enqueue and start a crawl run for domains that are due (pending/failed, when retry time allows)"
          >
            {queueM.isPending ? 'Working…' : 'Queue & crawl now'}
          </Button>
        </div>
        <p className="text-xs text-muted-foreground">
          {previewRows.length > 0
            ? `${selected.size} of ${previewRows.length} row(s) selected — queue sends the landing URL for each checked row. Re-preview after changing the phrase.`
            : 'Run a preview to see URLs.'}
        </p>
      </div>

      {lastQueue && lastQueue.queued > 0 ? (
        <div className="flex flex-wrap gap-2 rounded-lg border border-border bg-muted/30 p-3 text-sm">
          <span className="text-muted-foreground">Last action:</span>
          <Button size="sm" variant="outline" asChild>
            <Link to="/crawler/domains">Open domain queue</Link>
          </Button>
          {lastQueue.run_id != null ? (
            <Button size="sm" variant="outline" asChild>
              <Link to={`/crawler/runs/${lastQueue.run_id}`}>Open crawl run #{lastQueue.run_id}</Link>
            </Button>
          ) : null}
          <Button size="sm" variant="outline" asChild>
            <Link to="/crawler/runs">All crawl runs</Link>
          </Button>
        </div>
      ) : null}

      <div>
        <div className="mb-2 flex items-center justify-between gap-2">
          <h3 className="font-semibold text-foreground">Preview results</h3>
          {previewRows.length > 0 ? (
            <span className="text-xs text-muted-foreground">{previewRows.length} row(s)</span>
          ) : null}
        </div>
        <div className="overflow-auto rounded-lg border border-border">
          <table className="min-w-full text-sm">
            <thead className="bg-muted">
              <tr>
                <th className="w-10 px-2 py-2 text-left" aria-label="Select" />
                <th className="px-3 py-2 text-left">Site base</th>
                <th className="px-3 py-2 text-left">Landing URL (crawled first)</th>
                <th className="px-3 py-2 text-left">Actions</th>
              </tr>
            </thead>
            <tbody>
              {previewRows.length === 0 && !previewM.isPending ? (
                <tr>
                  <td colSpan={4} className="px-3 py-8 text-center text-muted-foreground">
                    No preview yet. Enter a phrase and click Preview URLs.
                  </td>
                </tr>
              ) : null}
              {previewM.isPending && previewRows.length === 0 ? (
                <tr>
                  <td colSpan={4} className="px-3 py-8 text-center text-muted-foreground">
                    Searching…
                  </td>
                </tr>
              ) : null}
              {previewRows.map((row) => (
                <tr key={row.id} className="border-t border-border">
                  <td className="px-2 py-2 align-middle">
                    <input
                      type="checkbox"
                      className="size-4 rounded border-border"
                      checked={selected.has(row.id)}
                      onChange={() => toggleRow(row.id)}
                      aria-label={`Include ${row.landing}`}
                    />
                  </td>
                  <td className="max-w-[10rem] truncate px-3 py-2 font-mono text-xs">{row.domain}</td>
                  <td className="max-w-0 px-3 py-2">
                    <a
                      className="break-all text-primary underline-offset-4 hover:underline"
                      href={row.landing}
                      target="_blank"
                      rel="noreferrer"
                    >
                      {row.landing}
                    </a>
                  </td>
                  <td className="whitespace-nowrap px-3 py-2">
                    <div className="flex flex-wrap gap-1">
                      <Button size="sm" variant="ghost" className="h-8 px-2" asChild title="Open in new tab">
                        <a href={row.landing} target="_blank" rel="noreferrer">
                          <ExternalLink className="size-3.5" aria-hidden />
                        </a>
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-8 px-2"
                        title="Copy landing URL"
                        onClick={() => void copyUrl(row.landing)}
                      >
                        <Copy className="size-3.5" aria-hidden />
                      </Button>
                      <Button
                        type="button"
                        size="sm"
                        variant="ghost"
                        className="h-8 px-2 text-destructive"
                        title="Remove from preview"
                        onClick={() => removeRow(row.id)}
                      >
                        <Trash2 className="size-3.5" aria-hidden />
                      </Button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>

        <div className="mt-3 flex flex-wrap items-end gap-2 rounded-md border border-dashed border-border bg-muted/20 p-3">
          <div className="min-w-[min(100%,320px)] flex-1">
            <label className="text-xs font-medium text-muted-foreground" htmlFor="manual-landing">
              Add landing URL manually
            </label>
            <input
              id="manual-landing"
              className="mt-1 h-9 w-full rounded-md border border-border bg-background px-3 text-sm"
              placeholder="https://example.org/events/… or tender detail page"
              value={manualUrl}
              onChange={(e) => setManualUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') addManualRow()
              }}
            />
          </div>
          <Button type="button" variant="outline" size="sm" className="h-9" onClick={addManualRow}>
            <Plus className="mr-1 size-4" aria-hidden />
            Add
          </Button>
        </div>
      </div>
    </div>
  )
}
