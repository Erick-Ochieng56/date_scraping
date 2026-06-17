import { useQuery } from '@tanstack/react-query'
import { AlertTriangle, PlugZap, Radio, Sparkles, Target, UserPlus } from 'lucide-react'
import { useEffect, useRef, useState } from 'react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from 'recharts'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/contexts/AuthContext'
import { fetchMetricsSummary } from '@/shared/api/metrics'
import { PageHeader } from '@/shared/components/PageHeader'
import { useRunsStream } from '@/shared/hooks/useRunsStream'

export function StaffHomePage() {
  const { me, isLoading: sessionLoading } = useAuth()
  const chartContainerRef = useRef<HTMLDivElement | null>(null)
  const [chartSize, setChartSize] = useState({ width: 0, height: 0 })

  const metricsQ = useQuery({
    queryKey: ['metrics-summary'],
    queryFn: fetchMetricsSummary,
    refetchInterval: 15_000,
  })

  const { transport } = useRunsStream(true)

  const sessionOk = Boolean(me?.authenticated && me.role === 'staff')
  const m = metricsQ.data

  const attentionItems: Array<{ label: string; value: number; to: string }> = []
  const failedCrawls = m?.failed_crawls_recent ?? 0
  if (failedCrawls > 0) {
    attentionItems.push({ label: 'Failed crawl runs (7d)', value: failedCrawls, to: '/crawler/runs?status=failed' })
  }
  const newProspects = m?.prospects_new ?? 0
  if (newProspects >= 25) {
    attentionItems.push({ label: 'New prospects to review', value: newProspects, to: '/prospects?status=new' })
  }

  useEffect(() => {
    const el = chartContainerRef.current
    if (!el) return

    const update = () => {
      setChartSize({
        width: Math.max(0, Math.floor(el.clientWidth)),
        height: Math.max(0, Math.floor(el.clientHeight)),
      })
    }

    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  return (
    <div className="space-y-6">
      <PageHeader
        title="Operations dashboard"
        description="Daily workflows for Scraper, Crawler, and Pipeline. Scraper runs are per-target; crawler uses the domain queue."
        actions={
          <>
            <span className="self-center text-xs text-muted-foreground">
              Runs updates: {transport === 'sse' ? 'live stream' : 'polling'}
            </span>
            <Button variant="outline" onClick={() => void metricsQ.refetch()}>
              Refresh
            </Button>
            <Button asChild>
              <Link to="/targets/new">Add scrape target</Link>
            </Button>
          </>
        }
      />

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Enabled targets</p>
          <p className="text-2xl font-semibold">{m?.targets_enabled ?? '—'}</p>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Scrape runs (7d)</p>
          <p className="text-2xl font-semibold">{m?.scrape_runs_recent ?? '—'}</p>
          <Link className="text-sm text-primary hover:underline" to="/runs">
            View runs
          </Link>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">Crawl runs (7d)</p>
          <p className="text-2xl font-semibold">{m?.crawl_runs_recent ?? '—'}</p>
          <Link className="text-sm text-primary hover:underline" to="/crawler/runs">
            View runs
          </Link>
        </div>
        <div className="rounded-lg border border-border bg-card p-4">
          <p className="text-sm text-muted-foreground">New prospects</p>
          <p className="text-2xl font-semibold">{m?.prospects_new ?? '—'}</p>
          <Link className="text-sm text-primary hover:underline" to="/prospects?status=new">
            Review queue
          </Link>
        </div>
      </div>

      {attentionItems.length > 0 ? (
        <div className="rounded-xl border border-amber-300/60 bg-amber-50/70 p-4 dark:border-amber-700/50 dark:bg-amber-950/20">
          <div className="flex items-center gap-2 text-amber-900 dark:text-amber-300">
            <AlertTriangle className="size-4 shrink-0" aria-hidden />
            <h3 className="font-semibold">Attention needed</h3>
          </div>
          <div className="mt-3 flex flex-wrap gap-2">
            {attentionItems.map((item) => (
              <Button key={item.label} size="sm" variant="outline" asChild>
                <Link to={item.to}>
                  {item.label}: {item.value}
                </Link>
              </Button>
            ))}
          </div>
        </div>
      ) : null}

      <div className="rounded-lg border border-border bg-card p-4">
        <h3 className="font-semibold text-foreground">Workflow shortcuts</h3>
        <div className="mt-3 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
          <div className="rounded-md border border-border bg-muted/30 p-3">
            <div className="flex items-center gap-2 font-medium text-foreground">
              <PlugZap className="size-4 text-primary" aria-hidden />
              Session
            </div>
            <p className="mt-1 text-sm text-muted-foreground">
              {sessionLoading && 'Checking session…'}
              {!sessionLoading && (sessionOk ? 'Signed in as staff.' : 'Session missing or unauthorized.')}
            </p>
          </div>
          <div className="rounded-md border border-border bg-muted/30 p-3">
            <div className="flex items-center gap-2 font-medium text-foreground">
              <Target className="size-4 text-primary" aria-hidden />
              Scraper
            </div>
            <p className="mt-1 text-sm text-muted-foreground">Configure targets and trigger manual scrapes.</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button size="sm" variant="outline" asChild>
                <Link to="/targets">Targets</Link>
              </Button>
              <Button size="sm" variant="outline" asChild>
                <Link to="/runs">Runs</Link>
              </Button>
            </div>
          </div>
          <div className="rounded-md border border-border bg-muted/30 p-3">
            <div className="flex items-center gap-2 font-medium text-foreground">
              <Radio className="size-4 text-primary" aria-hidden />
              Crawler
            </div>
            <p className="mt-1 text-sm text-muted-foreground">Discover domains and monitor crawl batches.</p>
            <div className="mt-2 flex flex-wrap gap-2">
              <Button size="sm" variant="outline" asChild>
                <Link to="/crawler/discover">Discover</Link>
              </Button>
              <Button size="sm" variant="outline" asChild>
                <Link to="/crawler">Overview</Link>
              </Button>
            </div>
          </div>
          <div className="rounded-md border border-border bg-muted/30 p-3">
            <div className="flex items-center gap-2 font-medium text-foreground">
              <UserPlus className="size-4 text-primary" aria-hidden />
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
        <div className="mt-3">
          <Button size="sm" variant="outline" asChild>
            <Link to="/crawler/ai-search">
              <Sparkles className="mr-1 inline size-3.5" aria-hidden />
              AI prospect search
            </Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="min-w-0 rounded-xl border border-border bg-card p-5">
          <h3 className="font-semibold text-foreground">Pipeline snapshot</h3>
          {m ? (
            <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-md bg-muted p-3">Contacted prospects: {m.prospects_contacted}</div>
              <div className="rounded-md bg-muted p-3">Interested leads: {m.leads_interested}</div>
              <div className="rounded-md bg-muted p-3">Synced to CRM: {m.leads_synced}</div>
              <div className="rounded-md bg-muted p-3">Scrape success (7d): {m.scrape_success_recent}</div>
            </div>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">Loading metrics…</p>
          )}
        </div>
        <div className="min-w-0 rounded-xl border border-border bg-card p-5">
          <h3 className="font-semibold text-foreground">Status distribution</h3>
          <div ref={chartContainerRef} className="mt-3 h-64 min-h-[16rem] min-w-0">
            {chartSize.width > 0 && chartSize.height > 0 ? (
              <BarChart
                width={chartSize.width}
                height={chartSize.height}
                data={[
                  ...(m?.prospect_status_breakdown ?? []).map((x) => ({ name: `P:${x.status}`, count: x.count })),
                  ...(m?.lead_status_breakdown ?? []).map((x) => ({ name: `L:${x.status}`, count: x.count })),
                ]}
              >
                <CartesianGrid strokeDasharray="3 3" />
                <XAxis dataKey="name" />
                <YAxis allowDecimals={false} />
                <Tooltip />
                <Bar dataKey="count" fill="currentColor" />
              </BarChart>
            ) : null}
          </div>
        </div>
      </div>
    </div>
  )
}
