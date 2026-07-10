import { useMutation, useQueryClient } from '@tanstack/react-query'
import { type ColumnDef } from '@tanstack/react-table'
import { Copy, ExternalLink, Plus, Search, Trash2, ChevronDown, ChevronRight } from 'lucide-react'
import { useMemo, useState } from 'react'

import { Button } from '@/components/ui/button'
import {
  DISCOVER_EXAMPLE_QUERIES,
  DISCOVER_MAX_OPTIONS,
  droppedToRows,
  hitsToRows,
  normalizeDiscoveryEntry,
  type DroppedRow,
  type PreviewRow,
  urlsToRows,
} from '@/features/crawler/discoverUtils'
import { invalidateCrawlerQueries } from '@/features/crawler/queryKeys'
import { getApiErrorMessage } from '@/shared/api/errors'
import { crawlerPreview, crawlerQueue } from '@/shared/api/crawler'
import { AlertBanner } from '@/shared/components/AlertBanner'
import { DataTable } from '@/shared/components/DataTable'
import { Input } from '@/shared/components/Input'
import { PageHeader } from '@/shared/components/PageHeader'
import { SectionEyebrow } from '@/shared/components/SectionEyebrow'
import { Select } from '@/shared/components/Select'
import { ExternalTextLink, TextLink } from '@/shared/components/TextLink'

const fieldClass = 'bg-background'

export function CrawlerDiscoverPage() {
  const qc = useQueryClient()
  const [query, setQuery] = useState('')
  const [maxResults, setMaxResults] = useState<number>(20)
  const [manualUrl, setManualUrl] = useState('')
  const [previewRows, setPreviewRows] = useState<PreviewRow[]>([])
  const [droppedRows, setDroppedRows] = useState<DroppedRow[]>([])
  const [showDropped, setShowDropped] = useState(false)
  const [selected, setSelected] = useState<Set<string>>(() => new Set())
  const [banner, setBanner] = useState<{ message?: string; error?: string }>({})
  const [lastQueue, setLastQueue] = useState<{
    queued: number
    new_domains: number
    run_id: number | null
  } | null>(null)

  const selectedLandings = useMemo(
    () => previewRows.filter((r) => selected.has(r.id)).map((r) => r.landing),
    [previewRows, selected]
  )

  const previewM = useMutation({
    mutationFn: () => crawlerPreview(query.trim(), maxResults),
    onMutate: () => {
      setBanner({})
      setLastQueue(null)
    },
    onSuccess: (data) => {
      const rows = data.hits && data.hits.length > 0 ? hitsToRows(data.hits) : urlsToRows(data.urls ?? [])
      const dropped = droppedToRows(data.dropped ?? [])
      setPreviewRows(rows)
      setDroppedRows(dropped)
      setShowDropped(dropped.length > 0 && rows.length === 0)
      setSelected(new Set(rows.map((r) => r.id)))
      if (rows.length === 0) {
        setBanner({
          message:
            dropped.length > 0
              ? `No URLs passed qualification — ${dropped.length} result(s) were filtered. Expand “Filtered out” below to see each URL and reason.`
              : 'No URLs returned — try a different phrase or check Serper/Bing configuration on the server.',
        })
      } else if (dropped.length > 0) {
        setBanner({
          message: `${rows.length} qualified URL(s) shown. ${dropped.length} Serp result(s) filtered out — see “Filtered out” below for details.`,
        })
      }
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
  })

  const queueM = useMutation({
    mutationFn: (withCrawl: boolean) =>
      crawlerQueue({
        query: query.trim(),
        max_results: maxResults,
        auto_crawl: withCrawl,
        urls: selectedLandings,
      }),
    onMutate: () => setBanner({}),
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
        : ' Domains are pending — start crawls from the domain queue or runs page.'
      setBanner({
        message: `Queued ${data.queued} domain(s), ${data.new_domains} new.${crawlNote}`,
      })
      invalidateCrawlerQueries(qc)
    },
    onError: (err) => setBanner({ error: getApiErrorMessage(err) }),
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
      setBanner({ error: 'Enter a valid URL or domain (deep links are kept).' })
      return
    }
    if (previewRows.some((r) => r.landing === landing)) {
      setBanner({ message: 'That URL is already in the preview list.' })
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
    setBanner({})
  }

  const clearPreview = () => {
    setPreviewRows([])
    setDroppedRows([])
    setShowDropped(false)
    setSelected(new Set())
    setLastQueue(null)
    setBanner({})
  }

  const copyUrl = async (u: string) => {
    try {
      await navigator.clipboard.writeText(u)
      setBanner({ message: 'Copied to clipboard.' })
    } catch {
      setBanner({ error: 'Could not copy.' })
    }
  }

  const previewColumns = useMemo<ColumnDef<PreviewRow, unknown>[]>(
    () => [
      {
        id: 'select',
        header: () => (
          <span className="sr-only">Select</span>
        ),
        cell: ({ row }) => (
          <input
            type="checkbox"
            className="size-4 rounded border-border"
            checked={selected.has(row.original.id)}
            onChange={() => toggleRow(row.original.id)}
            aria-label={`Include ${row.original.landing}`}
          />
        ),
      },
      {
        accessorKey: 'domain',
        header: 'Site base',
        cell: ({ row }) => (
          <span className="block max-w-[10rem] truncate font-mono text-xs">{row.original.domain}</span>
        ),
      },
      {
        accessorKey: 'landing',
        header: 'Landing URL (crawled first)',
        cell: ({ row }) => (
          <ExternalTextLink className="block break-all" href={row.original.landing}>
            {row.original.landing}
          </ExternalTextLink>
        ),
      },
      {
        id: 'actions',
        header: 'Actions',
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-1">
            <Button size="sm" variant="ghost" className="h-8 px-2" asChild title="Open in new tab">
              <a href={row.original.landing} target="_blank" rel="noreferrer">
                <ExternalLink className="size-3.5" aria-hidden />
              </a>
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-8 px-2"
              title="Copy landing URL"
              onClick={() => void copyUrl(row.original.landing)}
            >
              <Copy className="size-3.5" aria-hidden />
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-8 px-2 text-destructive"
              title="Remove from preview"
              onClick={() => removeRow(row.original.id)}
            >
              <Trash2 className="size-3.5" aria-hidden />
            </Button>
          </div>
        ),
      },
    ],
    [selected]
  )

  const droppedColumns = useMemo<ColumnDef<DroppedRow, unknown>[]>(
    () => [
      {
        accessorKey: 'domain',
        header: 'Site base',
        cell: ({ row }) => (
          <span className="block max-w-[10rem] truncate font-mono text-xs">{row.original.domain}</span>
        ),
      },
      {
        accessorKey: 'landing',
        header: 'Landing URL',
        cell: ({ row }) => (
          <ExternalTextLink className="block break-all" href={row.original.landing}>
            {row.original.landing}
          </ExternalTextLink>
        ),
      },
      {
        accessorKey: 'dropReason',
        header: 'Why filtered',
        cell: ({ row }) => <span className="text-muted-foreground">{row.original.dropReason}</span>,
      },
      {
        id: 'actions',
        header: 'Actions',
        cell: ({ row }) => (
          <div className="flex flex-wrap gap-1">
            <Button size="sm" variant="ghost" className="h-8 px-2" asChild title="Open in new tab">
              <a href={row.original.landing} target="_blank" rel="noreferrer">
                <ExternalLink className="size-3.5" aria-hidden />
              </a>
            </Button>
            <Button
              type="button"
              size="sm"
              variant="ghost"
              className="h-8 px-2"
              title="Copy landing URL"
              onClick={() => void copyUrl(row.original.landing)}
            >
              <Copy className="size-3.5" aria-hidden />
            </Button>
          </div>
        ),
      },
    ],
    []
  )

  return (
    <div className="space-y-6">
      <PageHeader
        title="Discover domains"
        description="Search the open web for sites to add to your crawler queue. Serp results keep the landing page URL (e.g. /events/…) so the crawler starts on that page. Preview, trim the list, then enqueue or enqueue + crawl."
      />

      <AlertBanner message={banner.message} error={banner.error} />

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="space-y-4 border-b border-border/80 px-4 py-4">
          <div className="flex flex-wrap items-end gap-3">
            <div className="min-w-[min(100%,280px)] flex-1">
              <SectionEyebrow>Search phrase</SectionEyebrow>
              <Input
                id="discover-query"
                className={`mt-2 ${fieldClass}`}
                placeholder='e.g. "translation events Kenya" or inurl:events site:.org …'
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                onKeyDown={(e) => {
                  if (e.key === 'Enter' && canPreview && !previewM.isPending) previewM.mutate()
                }}
              />
            </div>
            <div>
              <label className="text-[11px] font-semibold uppercase tracking-wide text-tertiary" htmlFor="discover-max">
                Max results
              </label>
              <Select
                id="discover-max"
                className={`mt-2 ${fieldClass}`}
                value={String(maxResults)}
                onChange={(e) => setMaxResults(Number(e.target.value))}
              >
                {DISCOVER_MAX_OPTIONS.map((n) => (
                  <option key={n} value={n}>
                    {n}
                  </option>
                ))}
              </Select>
            </div>
          </div>

          <div>
            <SectionEyebrow>Try an example</SectionEyebrow>
            <div className="mt-2 flex flex-wrap gap-2">
              {DISCOVER_EXAMPLE_QUERIES.map((ex) => (
                <Button
                  key={ex}
                  type="button"
                  size="sm"
                  variant="outline"
                  className={`h-8 text-xs ${fieldClass}`}
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
        </div>

        <div className="flex flex-wrap gap-2 border-b border-border/80 px-4 py-3">
          <Button disabled={!canPreview || previewM.isPending} onClick={() => previewM.mutate()}>
            <Search className="mr-1.5 size-4" aria-hidden />
            {previewM.isPending ? 'Searching…' : 'Preview URLs'}
          </Button>
          <Button type="button" variant="outline" className={fieldClass} disabled={previewRows.length === 0} onClick={clearPreview}>
            Clear preview
          </Button>
          <Button type="button" variant="outline" className={fieldClass} disabled={previewRows.length === 0} onClick={selectAll}>
            Select all
          </Button>
          <Button type="button" variant="outline" className={fieldClass} disabled={previewRows.length === 0} onClick={selectNone}>
            Select none
          </Button>
        </div>

        <div className="flex flex-wrap items-center justify-between gap-3 px-4 py-3">
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
              title="Enqueue and start a crawl run for domains that are due"
            >
              {queueM.isPending ? 'Working…' : 'Queue & crawl now'}
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            {previewRows.length > 0
              ? `${selected.size} of ${previewRows.length} selected`
              : 'Run a preview to see URLs'}
          </p>
        </div>
      </section>

      {lastQueue && lastQueue.queued > 0 ? (
        <section className="rounded-xl border border-border bg-card px-4 py-3">
          <SectionEyebrow>Last action</SectionEyebrow>
          <p className="mt-1 text-sm text-muted-foreground">
            Queued {lastQueue.queued} domain(s), {lastQueue.new_domains} new.
          </p>
          <div className="mt-2 flex flex-wrap gap-x-4 gap-y-1 text-sm">
            <TextLink to="/crawler/domains">Open domain queue</TextLink>
            {lastQueue.run_id != null ? (
              <TextLink to={`/crawler/runs/${lastQueue.run_id}`}>Open crawl run #{lastQueue.run_id}</TextLink>
            ) : null}
            <TextLink to="/crawler/runs">All crawl runs</TextLink>
          </div>
        </section>
      ) : null}

      <section className="overflow-hidden rounded-xl border border-border bg-card">
        <div className="flex items-center justify-between gap-2 border-b border-border/80 px-4 py-3">
          <SectionEyebrow>Preview results</SectionEyebrow>
          {previewRows.length > 0 ? (
            <span className="text-xs text-muted-foreground">{previewRows.length} row(s)</span>
          ) : null}
        </div>

        <DataTable
          surface="embedded"
          columns={previewColumns}
          data={previewRows}
          isLoading={previewM.isPending}
          emptyMessage="No preview yet. Enter a phrase and click Preview URLs."
          getRowId={(r) => r.id}
        />

        <div className="flex flex-wrap items-end gap-2 border-t border-border/80 px-4 py-3">
          <div className="min-w-[min(100%,320px)] flex-1">
            <label className="text-[11px] font-semibold uppercase tracking-wide text-tertiary" htmlFor="manual-landing">
              Add landing URL manually
            </label>
            <Input
              id="manual-landing"
              className={`mt-2 ${fieldClass}`}
              placeholder="https://example.org/events/… or tender detail page"
              value={manualUrl}
              onChange={(e) => setManualUrl(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter') addManualRow()
              }}
            />
          </div>
          <Button type="button" variant="outline" className={fieldClass} size="sm" onClick={addManualRow}>
            <Plus className="mr-1 size-4" aria-hidden />
            Add
          </Button>
        </div>
      </section>

      {droppedRows.length > 0 ? (
        <section className="overflow-hidden rounded-xl border border-border bg-card">
          <button
            type="button"
            className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left transition-colors hover:bg-muted/15"
            onClick={() => setShowDropped((open) => !open)}
            aria-expanded={showDropped}
          >
            <div className="flex items-center gap-2">
              {showDropped ? (
                <ChevronDown className="size-4 shrink-0 text-muted-foreground" aria-hidden />
              ) : (
                <ChevronRight className="size-4 shrink-0 text-muted-foreground" aria-hidden />
              )}
              <SectionEyebrow className="normal-case">Filtered out</SectionEyebrow>
              <span className="text-xs text-muted-foreground">
                {droppedRows.length} Serp result(s) did not pass qualification
              </span>
            </div>
          </button>
          {showDropped ? (
            <>
              <p className="border-t border-border/80 px-4 py-2 text-xs text-muted-foreground">
                These URLs were returned by search but rejected (past tenders, aggregators, LSP sellers, careers
                hubs, geo mismatch, PDFs, etc.).
              </p>
              <DataTable
                surface="embedded"
                columns={droppedColumns}
                data={droppedRows}
                emptyMessage="No filtered results."
                getRowId={(r) => r.id}
              />
            </>
          ) : null}
        </section>
      ) : null}
    </div>
  )
}
