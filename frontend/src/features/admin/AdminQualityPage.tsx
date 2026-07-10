import { useQuery } from '@tanstack/react-query'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { fetchQualityMetrics } from '@/shared/api/metrics'
import { PageHeader } from '@/shared/components/PageHeader'

const DROP_LABELS: Record<string, string> = {
  competitor: 'Competitor / LSP',
  geo: 'Geo filter',
  directory: 'Directory / aggregator',
  stale: 'Stale / archived',
  buyer_gate: 'Active buyer gate',
  other: 'Other',
}

export function AdminQualityPage() {
  const q = useQuery({
    queryKey: ['metrics-quality'],
    queryFn: fetchQualityMetrics,
    refetchInterval: 60_000,
  })

  const m = q.data
  const tiers = m?.prospect_score_tiers
  const drops = m?.discovery_drops

  return (
    <div className="space-y-6">
      <PageHeader
        title="Lead quality"
        description="Pipeline quality signals and discovery filter analytics (7-day window)."
        actions={
          <Button variant="outline" onClick={() => void q.refetch()}>
            Refresh
          </Button>
        }
      />

      <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">High-score new prospects</p>
          <p className="text-2xl font-semibold">{m?.prospects_high_score_new ?? '—'}</p>
          <Link className="text-sm text-primary hover:underline" to="/admin/pipeline?tab=prospects">
            Review pipeline
          </Link>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Enrichment backlog</p>
          <p className="text-2xl font-semibold">{m?.enrichment_backlog ?? '—'}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Ready to sync (interested)</p>
          <p className="text-2xl font-semibold">{m?.leads_ready_to_sync ?? '—'}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">New event prospects</p>
          <p className="text-2xl font-semibold">{m?.event_prospects_new ?? '—'}</p>
        </div>
      </div>

      {tiers ? (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="font-semibold">Prospect score distribution</h3>
          <div className="mt-3 grid gap-2 sm:grid-cols-4">
            <p>High (61+): <strong>{tiers.high}</strong></p>
            <p>Medium (31–60): <strong>{tiers.medium}</strong></p>
            <p>Low (0–30): <strong>{tiers.low}</strong></p>
            <p>Unscored: <strong>{tiers.unscored}</strong></p>
          </div>
        </div>
      ) : null}

      {m?.prospects_by_source?.length ? (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="font-semibold">Prospects by source</h3>
          <ul className="mt-2 space-y-1 text-sm">
            {m.prospects_by_source.map((row) => (
              <li key={row.source_name} className="flex justify-between gap-4">
                <span>{row.source_name}</span>
                <span className="font-medium tabular-nums">{row.count}</span>
              </li>
            ))}
          </ul>
        </div>
      ) : null}

      {drops ? (
        <div className="rounded-lg border border-border bg-card p-4">
          <h3 className="font-semibold">Discovery drops ({drops.period_days}d)</h3>
          <p className="mt-1 text-sm text-muted-foreground">
            From {drops.ai_search_jobs_analyzed} AI search job(s); ~{drops.total_drops_estimated} filtered candidates.
            Crawl competitors flagged: {m?.crawl_competitors_7d ?? 0}.
          </p>
          <div className="mt-3 grid gap-2 sm:grid-cols-2 lg:grid-cols-3">
            {Object.entries(drops.by_category).map(([key, count]) => (
              <div key={key} className="rounded-md border border-border px-3 py-2 text-sm">
                <p className="font-medium">{DROP_LABELS[key] ?? key}</p>
                <p className="text-2xl font-semibold tabular-nums">{count}</p>
                {(drops.sample_reasons[key] ?? []).slice(0, 1).map((reason) => (
                  <p key={reason} className="mt-1 text-xs text-muted-foreground line-clamp-2">
                    e.g. {reason}
                  </p>
                ))}
              </div>
            ))}
          </div>
        </div>
      ) : null}
    </div>
  )
}
