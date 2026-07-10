import { Link } from 'react-router-dom'

import { cn } from '@/lib/utils'

type KpiCardProps = {
  label: string
  value: number | null | undefined
  action?: string
  href?: string
  to?: string
}

export function KpiCard({ label, value, action, href, to }: KpiCardProps) {
  const display = value ?? '—'
  const isZero = value === 0
  const linkTarget = to ?? href

  const actionLink =
    action && linkTarget ? (
      to ? (
        <Link to={to} className="mt-2 inline-block text-sm font-medium text-info hover:underline">
          {action}
        </Link>
      ) : (
        <a href={href} className="mt-2 inline-block text-sm font-medium text-info hover:underline">
          {action}
        </a>
      )
    ) : null

  return (
    <div className="rounded-lg border border-border bg-card p-4">
      <p className="text-[11px] font-semibold uppercase tracking-wide text-tertiary">{label}</p>
      <p className={cn('mt-2 text-[28px] font-semibold leading-none', isZero ? 'text-tertiary' : 'text-foreground')}>
        {display}
      </p>
      {actionLink}
    </div>
  )
}
