import { useState } from 'react'

import { cn } from '@/lib/utils'
import type { MetricsGranularity, MetricsTimeseriesBucket } from '@/shared/api/types'

const SOURCES = [
  { key: 'site_check', label: 'Site checks', color: 'var(--chart-3)', className: 'bg-chart-3' },
  { key: 'web_crawler', label: 'Web crawler', color: 'var(--chart-2)', className: 'bg-chart-2' },
  { key: 'ai_search', label: 'AI search', color: 'var(--chart-1)', className: 'bg-chart-1' },
] as const

function parseLocalDate(iso: string) {
  const [y, m, d] = iso.split('-').map(Number)
  return new Date(y, m - 1, d)
}

function formatAxisLabel(iso: string, granularity: MetricsGranularity) {
  const d = parseLocalDate(iso)
  if (granularity === 'month') return d.toLocaleDateString(undefined, { month: 'short', year: '2-digit' })
  return d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })
}

function formatTooltipTitle(iso: string, granularity: MetricsGranularity) {
  const d = parseLocalDate(iso)
  if (granularity === 'month') return d.toLocaleDateString(undefined, { month: 'long', year: 'numeric' })
  if (granularity === 'week') {
    const end = new Date(d)
    end.setDate(end.getDate() + 6)
    return `Week of ${d.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })} – ${end.toLocaleDateString(undefined, { month: 'short', day: 'numeric' })}`
  }
  return d.toLocaleDateString(undefined, { weekday: 'short', month: 'short', day: 'numeric' })
}

function computeAxis(dataMax: number) {
  const safeMax = Math.max(1, dataMax)
  if (safeMax <= 4) return { max: 4, ticks: [0, 1, 2, 3, 4] }

  const rawStep = safeMax / 4
  const magnitude = Math.pow(10, Math.floor(Math.log10(rawStep)))
  const normalized = rawStep / magnitude
  const niceNormalized = normalized <= 1 ? 1 : normalized <= 2 ? 2 : normalized <= 5 ? 5 : 10
  const step = Math.max(1, Math.round(niceNormalized * magnitude))
  const max = Math.ceil(safeMax / step) * step

  const ticks: number[] = []
  for (let v = 0; v <= max; v += step) ticks.push(v)
  return { max, ticks }
}

type TooltipState = { bucket: MetricsTimeseriesBucket; x: number; y: number } | null

export function DiscoveriesChart({
  buckets,
  granularity,
}: {
  buckets: MetricsTimeseriesBucket[]
  granularity: MetricsGranularity
}) {
  const [tooltip, setTooltip] = useState<TooltipState>(null)

  const hasData = buckets.some((b) => b.prospects_total > 0)
  const { max, ticks } = computeAxis(Math.max(0, ...buckets.map((b) => b.prospects_total)))

  return (
    <div className="min-w-0">
      <div className="flex flex-wrap gap-x-5 gap-y-1.5">
        {SOURCES.map((s) => (
          <span key={s.key} className="inline-flex items-center gap-1.5 text-xs text-muted-foreground">
            <i className={cn('inline-block size-2.5 rounded-sm', s.className)} aria-hidden />
            {s.label}
          </span>
        ))}
      </div>

      {!hasData ? (
        <p className="mt-8 mb-8 text-center text-sm text-muted-foreground">
          No prospects found in this period yet.
        </p>
      ) : (
        <div className="relative mt-3 h-48">
          <div className="absolute inset-0 right-0 bottom-6 left-7">
            {ticks.map((t, i) => (
              <div
                key={t + i}
                className="absolute left-0 right-0 border-t border-border"
                style={{ top: `${(1 - t / max) * 100}%` }}
              >
                <span className="absolute -top-1.5 -left-7 w-6 text-right text-[10.5px] tabular-nums text-muted-foreground">
                  {t}
                </span>
              </div>
            ))}
          </div>

          <div className="absolute inset-0 right-0 bottom-6 left-7 flex items-stretch gap-[6%] px-[2%]">
            {buckets.map((b, i) => (
              <div
                key={b.date}
                className="relative flex flex-1 flex-col-reverse overflow-hidden rounded-t-sm"
                onMouseMove={(e) => setTooltip({ bucket: b, x: e.clientX, y: e.clientY })}
                onMouseLeave={() => setTooltip((t) => (t?.bucket === b ? null : t))}
              >
                {SOURCES.map((s) => {
                  const value = b.prospects_by_source[s.key]
                  if (!value) return null
                  return (
                    <div
                      key={s.key}
                      className="chart-grow-seg mt-[2px] w-full"
                      style={{
                        height: `${(value / max) * 100}%`,
                        backgroundColor: s.color,
                        animationDelay: `${Math.min(i, 10) * 0.04}s`,
                      }}
                    />
                  )
                })}
              </div>
            ))}
          </div>

          <div className="absolute inset-x-7 bottom-0 flex gap-[6%] px-[2%]">
            {buckets.map((b) => (
              <span key={b.date} className="flex-1 truncate text-center text-[11px] text-muted-foreground">
                {formatAxisLabel(b.date, granularity)}
              </span>
            ))}
          </div>
        </div>
      )}

      {tooltip ? (
        <div
          className="pointer-events-none fixed z-50 max-w-60 rounded-lg bg-foreground px-3 py-2 text-xs text-background shadow-lg"
          style={{ left: Math.min(tooltip.x + 14, window.innerWidth - 220), top: tooltip.y - 12 }}
        >
          <p className="mb-1 font-semibold">{formatTooltipTitle(tooltip.bucket.date, granularity)}</p>
          {SOURCES.map((s) => (
            <p key={s.key} className="flex items-center gap-1.5 tabular-nums">
              <i className={cn('inline-block size-2 rounded-sm', s.className)} aria-hidden />
              {s.label}: {tooltip.bucket.prospects_by_source[s.key]}
            </p>
          ))}
          <p className="mt-1 border-t border-background/20 pt-1 font-medium tabular-nums">
            Total: {tooltip.bucket.prospects_total}
          </p>
        </div>
      ) : null}
    </div>
  )
}
