import { Link } from 'react-router-dom'
import { AlertTriangle } from 'lucide-react'

import { cn } from '@/lib/utils'

export type AttentionItem = {
  label: string
  to: string
  action?: string
}

type AttentionPanelProps = {
  items: AttentionItem[]
  className?: string
}

export function AttentionPanel({ items, className }: AttentionPanelProps) {
  if (items.length === 0) {
    return (
      <div className={cn('rounded-lg border border-border bg-card px-4 py-5', className)}>
        <p className="text-[11px] font-semibold uppercase tracking-wide text-tertiary">Needs your review</p>
        <p className="mt-2 text-sm text-muted-foreground">Nothing waiting on you right now.</p>
      </div>
    )
  }

  return (
    <div
      className={cn(
        'rounded-lg border border-warning/30 bg-warning-bg px-4 py-4 dark:border-warning/40 dark:bg-warning/10',
        className
      )}
    >
      <div className="flex items-center gap-2 text-warning">
        <AlertTriangle className="size-4 shrink-0" aria-hidden />
        <p className="text-[11px] font-semibold uppercase tracking-wide">Needs your review</p>
      </div>
      <ul className="mt-3 space-y-2">
        {items.map((item) => (
          <li key={item.label} className="flex flex-wrap items-center justify-between gap-2 text-sm">
            <span className="text-foreground">{item.label}</span>
            <Link to={item.to} className="font-medium text-info hover:underline">
              {item.action ?? 'Review →'}
            </Link>
          </li>
        ))}
      </ul>
    </div>
  )
}
