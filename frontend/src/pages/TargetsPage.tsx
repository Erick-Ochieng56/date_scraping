import { useMemo, useState } from 'react'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { listTargets, triggerTarget, type Target } from '@/lib/api/dashboard'

function targetTypeLabel(v: string) {
  if (v === 'html') return 'HTML'
  if (v === 'playwright') return 'Playwright'
  return v
}

function hasItemSelector(config: Target['config'] | undefined): boolean {
  if (!config || typeof config !== 'object') return false
  const sel = config.item_selector ?? config.items_selector
  return typeof sel === 'string' && sel.length > 0
}

export function TargetsPage() {
  const qc = useQueryClient()
  const [search, setSearch] = useState('')
  const [enabledOnly, setEnabledOnly] = useState<boolean>(false)
  const [actionNote, setActionNote] = useState<string | null>(null)
  const [actionError, setActionError] = useState<string | null>(null)

  const targetsQ = useQuery({
    queryKey: ['targets', enabledOnly],
    queryFn: () => listTargets({ page_size: 200, enabled: enabledOnly ? true : undefined }),
  })

  const triggerOneM = useMutation({
    mutationFn: (targetId: number) => triggerTarget(targetId),
    onSuccess: (data) => {
      setActionError(null)
      setActionNote(data.message ?? 'Scrape queued.')
      void qc.invalidateQueries({ queryKey: ['targets'] })
      void qc.invalidateQueries({ queryKey: ['scrape-runs'] })
    },
    onError: (err: unknown) => {
      setActionNote(null)
      const ax = err as { response?: { data?: { error?: string } } }
      setActionError(ax.response?.data?.error ?? 'Could not start scrape.')
    },
  })

  const filtered = useMemo(() => {
    const rows = targetsQ.data?.items ?? []
    const q = search.trim().toLowerCase()
    if (!q) return rows
    return rows.filter(
      (t) =>
        t.name.toLowerCase().includes(q) ||
        t.target_type.toLowerCase().includes(q) ||
        t.start_url.toLowerCase().includes(q)
    )
  }, [targetsQ.data?.items, search])

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold text-foreground">Scrape targets</h2>
          <p className="mt-1 max-w-2xl text-sm text-muted-foreground">
            Each target is one listing page (URL + CSS selectors). Add targets here, configure selectors on the detail
            page, then run scrapes manually — there is no “scrape all” for staff.
          </p>
        </div>
        <Button asChild>
          <Link to="/targets/new">Add target</Link>
        </Button>
      </div>

      {(actionNote || actionError) && (
        <div className="rounded-md border border-border bg-muted/40 px-3 py-2 text-sm">
          {actionError ? <p className="text-destructive">{actionError}</p> : null}
          {actionNote && !actionError ? <p>{actionNote}</p> : null}
        </div>
      )}

      <div className="flex flex-wrap gap-2">
        <input
          className="h-9 min-w-[280px] rounded-md border border-border bg-background px-3 text-sm"
          placeholder="Search name, type, or URL..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
        <label className="inline-flex items-center gap-2 rounded-md border border-border px-3 text-sm">
          <input type="checkbox" checked={enabledOnly} onChange={(e) => setEnabledOnly(e.target.checked)} />
          Enabled only
        </label>
        <Button variant="outline" onClick={() => void qc.invalidateQueries({ queryKey: ['targets'] })}>
          Refresh
        </Button>
      </div>
      {targetsQ.isLoading ? <p className="text-sm text-muted-foreground">Loading targets...</p> : null}
      <div className="overflow-auto rounded-lg border border-border">
        <table className="min-w-full text-sm">
          <thead className="bg-muted">
            <tr>
              <th className="px-3 py-2 text-left">Name</th>
              <th className="px-3 py-2 text-left">Engine</th>
              <th className="px-3 py-2 text-left">Start URL</th>
              <th className="px-3 py-2 text-left">Selectors</th>
              <th className="px-3 py-2 text-left">Enabled</th>
              <th className="px-3 py-2 text-left">Schedule</th>
              <th className="px-3 py-2 text-left">Last run</th>
              <th className="px-3 py-2 text-left">Actions</th>
            </tr>
          </thead>
          <tbody>
            {filtered.map((target) => (
              <tr key={target.id} className="border-t border-border align-top">
                <td className="px-3 py-2 font-medium">{target.name}</td>
                <td className="px-3 py-2">{targetTypeLabel(target.target_type)}</td>
                <td className="max-w-[200px] px-3 py-2">
                  <a
                    className="break-all text-primary underline-offset-4 hover:underline"
                    href={target.start_url}
                    target="_blank"
                    rel="noreferrer"
                  >
                    {target.start_url}
                  </a>
                </td>
                <td className="px-3 py-2">
                  {hasItemSelector(target.config) ? (
                    <span className="rounded bg-muted px-2 py-0.5 text-xs">Ready</span>
                  ) : (
                    <span className="text-xs text-amber-700 dark:text-amber-400">Needs config</span>
                  )}
                </td>
                <td className="px-3 py-2">{target.enabled ? 'Yes' : 'No'}</td>
                <td className="px-3 py-2 whitespace-nowrap">Every {target.run_every_minutes} min</td>
                <td className="px-3 py-2 whitespace-nowrap">
                  {target.last_run_at ? new Date(target.last_run_at).toLocaleString() : '—'}
                </td>
                <td className="px-3 py-2">
                  <div className="flex flex-wrap gap-2">
                    <Button size="sm" variant="outline" asChild>
                      <Link to={`/targets/${target.id}`}>Configure</Link>
                    </Button>
                    <Button
                      size="sm"
                      disabled={triggerOneM.isPending}
                      onClick={() => {
                        setActionNote(null)
                        setActionError(null)
                        triggerOneM.mutate(target.id)
                      }}
                    >
                      Scrape now
                    </Button>
                    <Button size="sm" variant="ghost" className="h-8 px-2" asChild>
                      <Link to={`/runs?target_id=${target.id}`}>Runs</Link>
                    </Button>
                  </div>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
