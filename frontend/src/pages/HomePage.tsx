import { useEffect, useRef, useState } from 'react'
import { useQuery, useQueryClient } from '@tanstack/react-query'
import { AlertTriangle, PlugZap, Radio, Target, UserPlus } from 'lucide-react'
import { Link } from 'react-router-dom'
import { Bar, BarChart, CartesianGrid, Tooltip, XAxis, YAxis } from 'recharts'

import { Button } from '@/components/ui/button'
import { useAuth } from '@/contexts/AuthContext'
import { fetchMetricsSummary } from '@/lib/api/dashboard'

export function HomePage() {
  const qc = useQueryClient()
  const { me, isLoading: sessionLoading } = useAuth()
  const chartContainerRef = useRef<HTMLDivElement | null>(null)
  const [chartSize, setChartSize] = useState({ width: 0, height: 0 })

  const metricsQ = useQuery({
    queryKey: ['metrics-summary'],
    queryFn: fetchMetricsSummary,
    refetchInterval: 15000,
  })

  const sessionOk = Boolean(me?.authenticated && me.role === 'staff')
  const attentionItems: Array<{ label: string; value: number; to: string }> = []
  const failedCrawls = metricsQ.data?.failed_crawls_recent ?? 0
  if (failedCrawls > 0) {
    attentionItems.push({ label: 'Failed crawl runs (7d)', value: failedCrawls, to: '/crawler/runs?status=failed' })
  }
  const newProspects = metricsQ.data?.prospects_new ?? 0
  if (newProspects >= 25) {
    attentionItems.push({ label: 'New prospects to review', value: newProspects, to: '/prospects?status=new' })
  }

  useEffect(() => {
    const el = chartContainerRef.current
    if (!el) return

    const update = () => {
      const width = Math.max(0, Math.floor(el.clientWidth))
      const height = Math.max(0, Math.floor(el.clientHeight))
      setChartSize({ width, height })
    }

    update()
    const ro = new ResizeObserver(update)
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  return (
    <div className="space-y-8">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <h2 className="text-2xl font-semibold tracking-tight text-foreground">Operations dashboard</h2>
          <p className="mt-1 max-w-2xl text-muted-foreground">
            One place to run daily workflows for <strong>Scraper</strong>, <strong>Crawler</strong>, and{' '}
            <strong>Pipeline</strong>. Scraper stays manual per target; crawler remains queue/run based.
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Button variant="outline" onClick={() => void qc.invalidateQueries({ queryKey: ['metrics-summary'] })}>
            Refresh dashboard
          </Button>
          <Button asChild>
            <Link to="/targets/new">Add scrape target</Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center gap-2 text-foreground">
            <PlugZap className="size-5 text-primary" aria-hidden />
            <h3 className="font-semibold">Backend session</h3>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            {sessionLoading && 'Checking session…'}
            {!sessionLoading && (sessionOk ? 'Session OK — signed in as staff user.' : 'Session missing or unauthorized.')}
          </p>
          <p className="mt-3 text-xs text-muted-foreground">
            Staff access is limited to this React dashboard and API workflows.
          </p>
        </div>

        <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
          <div className="flex items-center gap-2 text-foreground">
            <Target className="size-5 text-primary" aria-hidden />
            <h3 className="font-semibold text-foreground">Scraper actions</h3>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">
            Create/configure target selectors and trigger manual per-target scrapes.
          </p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" variant="outline" asChild>
              <Link to="/targets">Open targets</Link>
            </Button>
            <Button size="sm" variant="outline" asChild>
              <Link to="/runs">Open scrape runs</Link>
            </Button>
          </div>
        </div>

        <div className="rounded-xl border border-border bg-card p-5 shadow-sm sm:col-span-2 lg:col-span-1">
          <div className="flex items-center gap-2 text-foreground">
            <Radio className="size-5 text-primary" aria-hidden />
            <h3 className="font-semibold text-foreground">Crawler actions</h3>
          </div>
          <p className="mt-2 text-sm text-muted-foreground">Discover domains, inspect queue, and monitor crawl runs.</p>
          <div className="mt-3 flex flex-wrap gap-2">
            <Button size="sm" variant="outline" asChild>
              <Link to="/crawler">Crawler home</Link>
            </Button>
            <Button size="sm" variant="outline" asChild>
              <Link to="/crawler/runs">Crawl runs</Link>
            </Button>
            <Button size="sm" variant="outline" asChild>
              <Link to="/crawler/domains">Domain queue</Link>
            </Button>
          </div>
        </div>
      </div>

      {attentionItems.length ? (
        <div className="rounded-xl border border-amber-300/60 bg-amber-50/70 p-4 shadow-sm dark:border-amber-700/50 dark:bg-amber-950/20">
          <div className="flex items-center gap-2 text-amber-900 dark:text-amber-300">
            <AlertTriangle className="size-4" aria-hidden />
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

      <div className="rounded-xl border border-border bg-card p-5 shadow-sm">
        <div className="flex items-center gap-2 text-foreground">
          <UserPlus className="size-5 text-primary" aria-hidden />
          <h3 className="font-semibold text-foreground">Pipeline actions</h3>
        </div>
        <p className="mt-2 text-sm text-muted-foreground">
          Move newly discovered prospects to qualified leads and keep CRM-ready records.
        </p>
        <div className="mt-3 flex flex-wrap gap-2">
          <Button size="sm" variant="outline" asChild>
            <Link to="/prospects">Open prospects</Link>
          </Button>
          <Button size="sm" variant="outline" asChild>
            <Link to="/leads">Open leads</Link>
          </Button>
        </div>
      </div>

      <div className="grid gap-4 lg:grid-cols-2">
        <div className="min-w-0 rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="font-semibold text-foreground">Pipeline snapshot</h3>
          {metricsQ.data ? (
            <div className="mt-3 grid grid-cols-2 gap-3 text-sm">
              <div className="rounded-md bg-muted p-3">Enabled targets: {metricsQ.data.targets_enabled}</div>
              <div className="rounded-md bg-muted p-3">Scrape runs (7d): {metricsQ.data.scrape_runs_recent}</div>
              <div className="rounded-md bg-muted p-3">New prospects: {metricsQ.data.prospects_new}</div>
              <div className="rounded-md bg-muted p-3">Interested leads: {metricsQ.data.leads_interested}</div>
            </div>
          ) : (
            <p className="mt-3 text-sm text-muted-foreground">Loading metrics...</p>
          )}
        </div>
        <div className="min-w-0 rounded-xl border border-border bg-card p-5 shadow-sm">
          <h3 className="font-semibold text-foreground">Status distribution</h3>
          <div ref={chartContainerRef} className="mt-3 h-64 min-h-[16rem] min-w-0">
            {chartSize.width > 0 && chartSize.height > 0 ? (
              <BarChart
                width={chartSize.width}
                height={chartSize.height}
                data={[
                  ...(metricsQ.data?.prospect_status_breakdown ?? []).map((x) => ({ name: `P:${x.status}`, count: x.count })),
                  ...(metricsQ.data?.lead_status_breakdown ?? []).map((x) => ({ name: `L:${x.status}`, count: x.count })),
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
