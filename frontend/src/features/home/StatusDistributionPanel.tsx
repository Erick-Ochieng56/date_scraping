import { useEffect, useMemo, useRef, useState } from 'react'
import { Bar, BarChart, CartesianGrid, Cell, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'

type StatusRow = { status: string; count: number }

const STATUS_COLOR: Record<string, string> = {
  new: 'var(--info)',
  contacted: 'var(--warning)',
  converted: 'var(--success)',
  interested: 'var(--success)',
  synced: 'var(--success)',
  rejected: '#9aa1b2',
  error: 'var(--primary)',
}

type StatusDistributionPanelProps = {
  prospectBreakdown: StatusRow[]
  leadBreakdown: StatusRow[]
}

function buildChartData(prospectBreakdown: StatusRow[], leadBreakdown: StatusRow[]) {
  const rows: Array<{ label: string; status: string; count: number }> = []
  for (const row of prospectBreakdown) {
    if (row.count > 0) rows.push({ label: `Prospect · ${row.status}`, status: row.status, count: row.count })
  }
  for (const row of leadBreakdown) {
    if (row.count > 0) rows.push({ label: `Lead · ${row.status}`, status: row.status, count: row.count })
  }
  return rows
}

export function StatusDistributionPanel({ prospectBreakdown, leadBreakdown }: StatusDistributionPanelProps) {
  const containerRef = useRef<HTMLDivElement | null>(null)
  const [mounted, setMounted] = useState(false)

  useEffect(() => {
    setMounted(true)
  }, [])

  const data = useMemo(() => buildChartData(prospectBreakdown, leadBreakdown), [prospectBreakdown, leadBreakdown])

  if (data.length === 0) {
    return (
      <p className="text-sm text-muted-foreground">
        No status data yet — run a scrape to see distribution here.
      </p>
    )
  }

  if (data.length === 1) {
    const only = data[0]
    return (
      <div className="flex flex-col gap-1 py-2">
        <span className="text-2xl font-semibold text-foreground">{only.count}</span>
        <span className="text-sm text-muted-foreground">{only.label}</span>
      </div>
    )
  }

  if (!mounted) {
    return <div ref={containerRef} className="h-[220px]" />
  }

  return (
    <div ref={containerRef} className="h-[220px] min-w-0">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} barSize={28}>
          <CartesianGrid vertical={false} stroke="var(--border)" />
          <XAxis dataKey="label" tickLine={false} axisLine={false} fontSize={12} interval={0} angle={-20} textAnchor="end" height={56} />
          <YAxis allowDecimals={false} tickLine={false} axisLine={false} fontSize={12} width={28} />
          <Tooltip />
          <Bar dataKey="count" radius={[4, 4, 0, 0]}>
            {data.map((row) => (
              <Cell key={row.label} fill={STATUS_COLOR[row.status] ?? 'var(--border)'} />
            ))}
          </Bar>
        </BarChart>
      </ResponsiveContainer>
    </div>
  )
}
