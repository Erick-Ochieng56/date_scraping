import { formatDistanceToNow } from 'date-fns'
import { useQuery } from '@tanstack/react-query'
import { PlugZap, Radio, Sparkles, Target, UserPlus } from 'lucide-react'
import { Link } from 'react-router-dom'

import { AttentionPanel, type AttentionItem } from '@/features/home/AttentionPanel'
import { RecentNotificationsPanel } from '@/features/home/RecentNotificationsPanel'
import { StatusDistributionPanel } from '@/features/home/StatusDistributionPanel'
import { Button } from '@/components/ui/button'
import { useAuth } from '@/contexts/AuthContext'
import { fetchMetricsSummary, fetchQualityMetrics } from '@/shared/api/metrics'
import { KpiCard } from '@/shared/components/KpiCard'
import { PageHeader } from '@/shared/components/PageHeader'
import { SectionEyebrow } from '@/shared/components/SectionEyebrow'
import { useRunsStream } from '@/shared/hooks/useRunsStream'

export function StaffHomePage() {
  const { me, isLoading: sessionLoading } = useAuth()

  const metricsQ = useQuery({
    queryKey: ['metrics-summary'],
    queryFn: fetchMetricsSummary,
    refetchInterval: 15_000,
  })

  const qualityQ = useQuery({
    queryKey: ['metrics-quality'],
    queryFn: fetchQualityMetrics,
    refetchInterval: 60_000,
  })

  useRunsStream(true)

  const sessionOk = Boolean(me?.authenticated && me.role === 'staff')
  const m = metricsQ.data
  const q = qualityQ.data

  const updatedLabel = metricsQ.isFetching
    ? 'Updating…'
    : metricsQ.dataUpdatedAt
      ? `Updated ${formatDistanceToNow(metricsQ.dataUpdatedAt, { addSuffix: true })}`
      : '—'

  const attentionItems: AttentionItem[] = []
  const failedCrawls = m?.failed_crawls_recent ?? 0
  if (failedCrawls > 0) {
    attentionItems.push({
      label: `${failedCrawls} failed crawl run${failedCrawls === 1 ? '' : 's'} (7d)`,
      to: '/crawler/runs?status=failed',
      action: 'View crawl runs →',
    })
  }

  const highScoreNew = q?.prospects_high_score_new ?? 0
  const newProspects = m?.prospects_new ?? 0
  if (highScoreNew > 0) {
    attentionItems.push({
      label: `${highScoreNew} high-score prospect${highScoreNew === 1 ? '' : 's'} (≥60)`,
      to: '/prospects?status=new&sort=score&min_score=60',
      action: 'Review prospects →',
    })
  } else if (newProspects > 0) {
    attentionItems.push({
      label: `${newProspects} new prospect${newProspects === 1 ? '' : 's'} to review`,
      to: '/prospects?status=new',
      action: 'Review prospects →',
    })
  }

  const enrichmentBacklog = q?.enrichment_backlog ?? 0
  if (enrichmentBacklog > 0) {
    attentionItems.push({
      label: `${enrichmentBacklog} in enrichment backlog`,
      to: '/prospects?status=new',
      action: 'Review prospects →',
    })
  }

  const readySync = q?.leads_ready_to_sync ?? 0
  if (readySync > 0) {
    attentionItems.push({
      label: `${readySync} lead${readySync === 1 ? '' : 's'} ready for CRM`,
      to: '/leads?status=interested',
      action: 'View interested leads →',
    })
  }

  const eventProspectsNew = q?.event_prospects_new ?? 0
  if (eventProspectsNew > 0) {
    attentionItems.push({
      label: `${eventProspectsNew} new event prospect${eventProspectsNew === 1 ? '' : 's'}`,
      to: '/event-prospects',
      action: 'Review events →',
    })
  }

  return (
    <div className="space-y-8">
      <PageHeader
        title="Operations dashboard"
        description="Daily workflows for Scraper, Crawler, and Pipeline."
        actions={
          <>
            <span className="self-center text-xs text-tertiary">{updatedLabel}</span>
            <Button variant="outline" onClick={() => void Promise.all([metricsQ.refetch(), qualityQ.refetch()])}>
              Refresh
            </Button>
            <Button asChild>
              <Link to="/targets/new">Add scrape target</Link>
            </Button>
          </>
        }
      />

      <section className="space-y-3">
        <SectionEyebrow>Throughput (7d)</SectionEyebrow>
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <KpiCard label="Enabled targets" value={m?.targets_enabled ?? null} />
          <KpiCard
            label="Scrape runs"
            value={m?.scrape_runs_recent ?? null}
            action="View scrape runs"
            to="/runs"
          />
          <KpiCard
            label="Crawl runs"
            value={m?.crawl_runs_recent ?? null}
            action="View crawl runs"
            to="/crawler/runs"
          />
          <KpiCard
            label="New prospects"
            value={m?.prospects_new ?? null}
            action={newProspects > 0 ? `Review ${newProspects} prospect${newProspects === 1 ? '' : 's'}` : undefined}
            to={newProspects > 0 ? '/prospects?status=new' : undefined}
          />
        </div>
      </section>

      <AttentionPanel items={attentionItems} />

      <RecentNotificationsPanel />

      <section className="space-y-3">
        <SectionEyebrow>Workflow shortcuts</SectionEyebrow>
        <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-lg border border-border bg-card p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <PlugZap className="size-4 text-secondary" aria-hidden />
              Session
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {sessionLoading && 'Checking session…'}
              {!sessionLoading && (sessionOk ? 'Signed in as staff.' : 'Session missing or unauthorized.')}
            </p>
          </div>
          <div className="rounded-lg border border-border bg-card p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Target className="size-4 text-secondary" aria-hidden />
              Scraper
            </div>
            <p className="mt-1 text-sm text-muted-foreground">Configure targets and trigger manual scrapes.</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button size="sm" variant="outline" asChild>
                <Link to="/targets">Scrape targets</Link>
              </Button>
              <Button size="sm" variant="outline" asChild>
                <Link to="/runs">Scrape runs</Link>
              </Button>
            </div>
          </div>
          <div className="rounded-lg border border-border bg-card p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <Radio className="size-4 text-secondary" aria-hidden />
              Crawler
            </div>
            <p className="mt-1 text-sm text-muted-foreground">Discover domains and monitor crawl batches.</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button size="sm" variant="outline" asChild>
                <Link to="/crawler/discover">Discover domains</Link>
              </Button>
              <Button size="sm" variant="outline" asChild>
                <Link to="/crawler/runs">Crawl runs</Link>
              </Button>
            </div>
          </div>
          <div className="rounded-lg border border-border bg-card p-3">
            <div className="flex items-center gap-2 text-sm font-medium text-foreground">
              <UserPlus className="size-4 text-secondary" aria-hidden />
              Pipeline
            </div>
            <p className="mt-1 text-sm text-muted-foreground">Qualify prospects and sync interested leads.</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button size="sm" variant="outline" asChild>
                <Link to="/prospects">Prospects</Link>
              </Button>
              <Button size="sm" variant="outline" asChild>
                <Link to="/leads">Leads</Link>
              </Button>
            </div>
          </div>
        </div>
        <Button size="sm" variant="outline" asChild>
          <Link to="/crawler/ai-search">
            <Sparkles className="mr-1 inline size-3.5" aria-hidden />
            AI prospect search
          </Link>
        </Button>
      </section>

      <section className="grid gap-4 lg:grid-cols-2">
        <div className="min-w-0 rounded-lg border border-border bg-card p-5">
          <SectionEyebrow>Pipeline snapshot</SectionEyebrow>
          {m ? (
            <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-md bg-muted/60 px-3 py-2 text-muted-foreground">
                Contacted prospects: <span className="font-medium text-foreground">{m.prospects_contacted}</span>
              </div>
              <div className="rounded-md bg-muted/60 px-3 py-2 text-muted-foreground">
                Interested leads: <span className="font-medium text-foreground">{m.leads_interested}</span>
              </div>
              <div className="rounded-md bg-muted/60 px-3 py-2 text-muted-foreground">
                Synced to CRM: <span className="font-medium text-foreground">{m.leads_synced}</span>
              </div>
              <div className="rounded-md bg-muted/60 px-3 py-2 text-muted-foreground">
                Scrape success (7d): <span className="font-medium text-foreground">{m.scrape_success_recent}</span>
              </div>
            </div>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">Loading metrics…</p>
          )}
        </div>
        <div className="min-w-0 rounded-lg border border-border bg-card p-5">
          <SectionEyebrow>Status distribution</SectionEyebrow>
          <div className="mt-3">
            <StatusDistributionPanel
              prospectBreakdown={m?.prospect_status_breakdown ?? []}
              leadBreakdown={m?.lead_status_breakdown ?? []}
            />
          </div>
        </div>
      </section>
    </div>
  )
}
