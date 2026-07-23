import { useQuery } from '@tanstack/react-query'
import { AlertTriangle } from 'lucide-react'
import { useState } from 'react'
import { Link } from 'react-router-dom'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/contexts/AuthContext'
import { cn } from '@/lib/utils'
import { listAiSearchJobs, listCrawlRuns } from '@/shared/api/crawler'
import { fetchMetricsSummary, fetchMetricsTimeseries } from '@/shared/api/metrics'
import { listScrapeRuns } from '@/shared/api/scraper'
import type { AISearchJob, CrawlRun, MetricsGranularity, ScrapeRun } from '@/shared/api/types'
import { DiscoveriesChart } from '@/shared/components/DiscoveriesChart'
import { PageHeader } from '@/shared/components/PageHeader'
import { useRunsStream } from '@/shared/hooks/useRunsStream'
import { summarizeAiSearchJob, summarizeCrawlRun, summarizeScrapeRun } from '@/shared/utils/runSummary'

function capitalize(s: string) {
  return s ? s[0].toUpperCase() + s.slice(1) : s
}

function greeting() {
  const hour = new Date().getHours()
  if (hour < 12) return 'Good morning'
  if (hour < 18) return 'Good afternoon'
  return 'Good evening'
}

function todayEyebrow() {
  return new Date().toLocaleDateString(undefined, { weekday: 'long', day: 'numeric', month: 'long' })
}

function formatRelative(iso: string) {
  const diffMs = Date.now() - new Date(iso).getTime()
  const mins = Math.round(diffMs / 60_000)
  if (mins < 1) return 'just now'
  if (mins < 60) return `${mins}m ago`
  const hours = Math.round(mins / 60)
  if (hours < 24) return `${hours}h ago`
  const days = Math.round(hours / 24)
  if (days === 1) return 'yesterday'
  if (days < 7) return `${days}d ago`
  return new Date(iso).toLocaleDateString()
}

type ActivityItem = { id: string; color: string; text: string; at: string }

function scrapeRunActivity(run: ScrapeRun): ActivityItem | null {
  if (run.status === 'running') return null
  return {
    id: `scrape-${run.id}`,
    color: run.status === 'failed' ? 'bg-destructive' : 'bg-chart-3',
    text: summarizeScrapeRun(run),
    at: run.started_at,
  }
}

function crawlRunActivity(run: CrawlRun): ActivityItem | null {
  if (run.status === 'running') return null
  return {
    id: `crawl-${run.id}`,
    color: run.status === 'failed' ? 'bg-destructive' : 'bg-chart-2',
    text: summarizeCrawlRun(run),
    at: run.started_at,
  }
}

function aiSearchActivity(job: AISearchJob): ActivityItem | null {
  if (job.status !== 'done' && job.status !== 'failed') return null
  return {
    id: `ai-${job.id}`,
    color: job.status === 'failed' ? 'bg-destructive' : 'bg-chart-1',
    text: summarizeAiSearchJob(job),
    at: job.created_at,
  }
}

const GRANULARITIES: { value: MetricsGranularity; label: string }[] = [
  { value: 'day', label: 'Day' },
  { value: 'week', label: 'Week' },
  { value: 'month', label: 'Month' },
]

const RANGE_CAPTION: Record<MetricsGranularity, string> = {
  day: 'last 14 days',
  week: 'last 8 weeks',
  month: 'last 6 months',
}

function Sparkline({ values, color }: { values: number[]; color: string }) {
  const width = 96
  const height = 30
  const max = Math.max(1, ...values)
  const step = values.length > 1 ? width / (values.length - 1) : 0
  const points = values
    .map((v, i) => `${(i * step).toFixed(1)},${(height - 4 - (v / max) * (height - 8)).toFixed(1)}`)
    .join(' ')
  const last = points.split(' ').at(-1)?.split(',').map(Number) ?? [width - 2, height / 2]

  return (
    <svg className="h-[30px] w-24 shrink-0" viewBox={`0 0 ${width} ${height}`} aria-hidden="true">
      <polyline fill="none" stroke={color} strokeWidth="2" points={points} />
      <circle cx={last[0]} cy={last[1]} r="3" fill={color} />
    </svg>
  )
}

export function StaffHomePage() {
  const { me } = useAuth()
  const name = me && 'username' in me ? me.username : undefined
  const [granularity, setGranularity] = useState<MetricsGranularity>('day')

  const metricsQ = useQuery({
    queryKey: ['metrics-summary'],
    queryFn: fetchMetricsSummary,
    refetchInterval: 15_000,
  })
  const weeklyQ = useQuery({
    queryKey: ['metrics-timeseries', 'day', 7],
    queryFn: () => fetchMetricsTimeseries('day', 7),
  })
  const timeseriesQ = useQuery({
    queryKey: ['metrics-timeseries', granularity],
    queryFn: () => fetchMetricsTimeseries(granularity),
  })
  const scrapeRunsQ = useQuery({
    queryKey: ['scrape-runs', 'home-activity'],
    queryFn: () => listScrapeRuns({ page_size: 5 }),
  })
  const crawlRunsQ = useQuery({
    queryKey: ['crawler', 'runs', 'home-activity'],
    queryFn: () => listCrawlRuns({ page_size: 5 }),
  })
  const aiSearchQ = useQuery({
    queryKey: ['ai-search', 'jobs', 'home-activity'],
    queryFn: () => listAiSearchJobs({ page_size: 5 }),
    refetchInterval: 30_000,
  })

  // Keeps run-related queries fresh in the background (SSE with polling fallback);
  // no need to surface which transport is active to the user.
  useRunsStream(true)

  const m = metricsQ.data
  const newProspects = m?.prospects_new ?? 0
  const failedCrawls = m?.failed_crawls_recent ?? 0

  const weekBuckets = weeklyQ.data?.buckets ?? []
  const prospectsThisWeek = weekBuckets.reduce((sum, b) => sum + b.prospects_total, 0)
  const prospectsSparkline = weekBuckets.map((b) => b.prospects_total)

  const buckets = timeseriesQ.data?.buckets ?? []

  const activity = [
    ...(scrapeRunsQ.data?.items ?? []).flatMap((r) => scrapeRunActivity(r) ?? []),
    ...(crawlRunsQ.data?.items ?? []).flatMap((r) => crawlRunActivity(r) ?? []),
    ...(aiSearchQ.data?.items ?? []).flatMap((j) => aiSearchActivity(j) ?? []),
  ]
    .sort((a, b) => new Date(b.at).getTime() - new Date(a.at).getTime())
    .slice(0, 6)

  const activityLoading = scrapeRunsQ.isLoading || crawlRunsQ.isLoading || aiSearchQ.isLoading
  const activityAllFailed = scrapeRunsQ.isError && crawlRunsQ.isError && aiSearchQ.isError

  return (
    <div className="space-y-6">
      <PageHeader
        eyebrow={todayEyebrow()}
        title={`${greeting()}${name ? `, ${capitalize(name)}` : ''}`}
        description={
          newProspects > 0 ? (
            <>
              <b className="font-semibold text-foreground">{newProspects}</b> new prospect
              {newProspects === 1 ? '' : 's'} {newProspects === 1 ? 'is' : 'are'} waiting for your review.
            </>
          ) : (
            "You're all caught up — nothing new to review right now."
          )
        }
        actions={
          <>
            <Button asChild>
              <Link to="/prospects">Start reviewing</Link>
            </Button>
            <Button variant="outline" asChild>
              <Link to="/find-leads">Find more leads</Link>
            </Button>
          </>
        }
      />

      {failedCrawls > 0 ? (
        <div
          role="alert"
          className="flex items-center gap-3 rounded-xl border border-destructive/30 border-l-4 border-l-destructive bg-destructive/10 px-4 py-3 text-sm"
        >
          <AlertTriangle className="size-4 shrink-0 text-destructive" aria-hidden />
          <span>
            {failedCrawls} web crawler run{failedCrawls === 1 ? '' : 's'} didn't finish this week.
          </span>
          <Link to="/crawler/runs?status=failed" className="ml-auto shrink-0 font-medium text-destructive hover:underline">
            View details
          </Link>
        </div>
      ) : null}

      <div className="grid gap-4 sm:grid-cols-3">
        <div className="flex items-end justify-between gap-3 rounded-xl border border-border bg-card p-4">
          <div>
            <p className="text-sm text-muted-foreground">New prospects this week</p>
            <p className="text-[28px] font-semibold leading-tight tabular-nums text-foreground">{prospectsThisWeek}</p>
          </div>
          {prospectsSparkline.some((v) => v > 0) ? <Sparkline values={prospectsSparkline} color="var(--chart-1)" /> : null}
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Contacted this week</p>
          <p className="text-[28px] font-semibold leading-tight tabular-nums text-foreground">
            {m?.prospects_contacted_recent ?? 0}
          </p>
        </div>
        <div className="rounded-xl border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Interested leads</p>
          <p className="text-[28px] font-semibold leading-tight tabular-nums text-foreground">{m?.leads_interested ?? 0}</p>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-5">
        <div className="min-w-0 rounded-xl border border-border bg-card p-5 lg:col-span-3">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <h3 className="font-semibold text-foreground">Where prospects came from</h3>
              <p className="mt-1 text-sm text-muted-foreground">
                Discoveries by the feature that found them — {RANGE_CAPTION[granularity]}.
              </p>
            </div>
            <div className="flex rounded-lg border border-border p-0.5">
              {GRANULARITIES.map((g) => (
                <button
                  key={g.value}
                  type="button"
                  onClick={() => setGranularity(g.value)}
                  aria-pressed={granularity === g.value}
                  className={cn(
                    'rounded-md px-2.5 py-1 text-xs font-medium transition-colors',
                    granularity === g.value
                      ? 'bg-primary text-primary-foreground'
                      : 'text-muted-foreground hover:text-foreground'
                  )}
                >
                  {g.label}
                </button>
              ))}
            </div>
          </div>

          <div className="mt-4">
            {timeseriesQ.isLoading ? (
              <p className="text-sm text-muted-foreground">Loading chart…</p>
            ) : timeseriesQ.isError ? (
              <p className="text-sm text-destructive" role="alert">
                Couldn't load the chart.
              </p>
            ) : (
              <DiscoveriesChart buckets={buckets} granularity={granularity} />
            )}
          </div>
        </div>

        <div className="min-w-0 rounded-xl border border-border bg-card p-5 lg:col-span-2">
          <h3 className="font-semibold text-foreground">Latest activity</h3>
          <p className="mt-1 text-sm text-muted-foreground">What the system did for you recently.</p>
          {activityLoading ? (
            <p className="mt-4 text-sm text-muted-foreground">Loading recent activity…</p>
          ) : activityAllFailed ? (
            <p className="mt-4 text-sm text-destructive" role="alert">
              Couldn't load recent activity.
            </p>
          ) : activity.length === 0 ? (
            <p className="mt-4 text-sm text-muted-foreground">No recent activity yet — try Find more leads to get started.</p>
          ) : (
            <ul className="mt-3">
              {activity.map((item, i) => (
                <li key={item.id} className={cn('flex items-start gap-3 py-2.5 text-sm', i > 0 && 'border-t border-border')}>
                  <span className={cn('mt-1.5 size-2 shrink-0 rounded-full', item.color)} aria-hidden />
                  <span className="flex-1">{item.text}</span>
                  <span className="shrink-0 whitespace-nowrap text-xs text-muted-foreground">{formatRelative(item.at)}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  )
}
